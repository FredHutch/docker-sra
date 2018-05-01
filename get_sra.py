#!/usr/bin/env python3

import os
import sys
import uuid
import shutil
import logging
import argparse
import traceback
import subprocess


def exit_and_clean_up(temp_folder):
    """Log the error messages and delete the temporary folder."""
    # Capture the traceback
    logging.info("There was an unexpected failure")
    exc_type, exc_value, exc_traceback = sys.exc_info()
    for line in traceback.format_tb(exc_traceback):
        logging.info(line)

    # Delete any files that were created for this sample
    logging.info("Removing temporary folder: " + temp_folder)
    shutil.rmtree(temp_folder)

    # Exit
    logging.info("Exit type: {}".format(exc_type))
    logging.info("Exit code: {}".format(exc_value))
    sys.exit(exc_value)


def run_cmds(commands, retry=0, catchExcept=False, stdout=None):
    """Run commands and write out the log, combining STDOUT & STDERR."""
    logging.info("Commands:")
    logging.info(' '.join(commands))
    if stdout is None:
        p = subprocess.Popen(commands,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        stdout, stderr = p.communicate()
    else:
        with open(stdout, "wt") as fo:
            p = subprocess.Popen(commands,
                                 stderr=subprocess.PIPE,
                                 stdout=fo)
            stdout, stderr = p.communicate()
        stdout = False
    exitcode = p.wait()
    if stdout:
        logging.info("Standard output of subprocess:")
        for line in stdout.decode("latin-1").split('\n'):
            logging.info(line)
    if stderr:
        logging.info("Standard error of subprocess:")
        for line in stderr.decode("latin-1").split('\n'):
            logging.info(line)

    # Check the exit code
    if exitcode != 0 and retry > 0:
        msg = "Exit code {}, retrying {} more times".format(exitcode, retry)
        logging.info(msg)
        run_cmds(commands, retry=retry - 1)
    elif exitcode != 0 and catchExcept:
        msg = "Exit code was {}, but we will continue anyway"
        logging.info(msg.format(exitcode))
    else:
        assert exitcode == 0, "Exit code {}".format(exitcode)


def set_up_sra_cache_folder(temp_folder):
    """Set up the fastq-dump cache folder within the temp folder."""
    logging.info("Setting up fastq-dump cache within {}".format(temp_folder))
    for path in [
        "/root/ncbi",
        "/root/ncbi/public"
    ]:
        if os.path.exists(path) is False:
            os.mkdir(path)

    if os.path.exists("/root/ncbi/public/sra"):
        shutil.rmtree("/root/ncbi/public/sra")

    # Now make a folder within the temp folder
    temp_cache = os.path.join(temp_folder, "sra")
    assert os.path.exists(temp_cache) is False
    os.mkdir(temp_cache)

    # Symlink it to /root/ncbi/public/sra/
    run_cmds(["ln", "-s", "-f", temp_cache, "/root/ncbi/public/sra"])

    assert os.path.exists("/root/ncbi/public/sra")


def interleave_fastq(fwd_fp, rev_fp, comb_fp):
    fwd = open(fwd_fp, "rt")
    rev = open(rev_fp, "rt")
    nreads = 0
    with open(comb_fp, "wt") as fo:
        while True:
            fwd_read = [fwd.readline() for ix in range(4)]
            rev_read = [rev.readline() for ix in range(4)]
            if any([l == '' for l in fwd_read]):
                break
            assert any([l == '' for l in rev_read]) is False
            nreads += 1
            fo.write(''.join(fwd_read))
            fo.write(''.join(rev_read))
    fwd.close()
    rev.close()
    logging.info("Interleaved {:,} pairs of reads".format(nreads))


def get_sra(accession, temp_folder):
    """Get the FASTQ for an SRA accession."""
    logging.info("Downloading {} from SRA".format(accession))

    local_path = os.path.join(temp_folder, accession + ".fastq")
    logging.info("Local path: {}".format(local_path))

    # Download via fastq-dump
    logging.info("Downloading via fastq-dump")
    run_cmds([
        "prefetch", accession
    ])
    # Output the _1.fastq and _2.fastq files
    run_cmds([
        "fastq-dump", "--split-files", 
        "--defline-seq", "@$ac.$si.$sg/$ri", 
        "--defline-qual", "+", 
        "--outdir", temp_folder, accession
    ])
    r1 = os.path.join(temp_folder, accession + "_1.fastq")
    r2 = os.path.join(temp_folder, accession + "_2.fastq")
    assert os.path.exists(r1)

    # If there are two reads created, interleave them
    if os.path.exists(r2):
        r1_paired = os.path.join(temp_folder, accession + "_1.fastq.paired.fq")
        r2_paired = os.path.join(temp_folder, accession + "_2.fastq.paired.fq")

        # Isolate the properly paired filed
        run_cmds([
            "fastq_pair", r1, r2
        ])
        assert os.path.exists(r1_paired)
        assert os.path.exists(r2_paired)
        logging.info("Removing raw downloaded FASTQ files")
        os.remove(r1)
        os.remove(r2)

        # Interleave the two paired files
        logging.info("Interleaving the paired FASTQ files")
        interleave_fastq(r1_paired, r2_paired, local_path)
        assert os.path.exists(local_path)
        logging.info("Removing split and filtered FASTQ files")
        os.remove(r1_paired)
        os.remove(r2_paired)
    else:
        # Otherwise, just make the _1.fastq file the output
        logging.info("Using {} as the output file".format(r1))
        run_cmds(["mv", r1, local_fp])

    # Remove the cache file, if any
    cache_fp = "/root/ncbi/public/sra/{}.sra".format(accession)
    if os.path.exists(cache_fp):
        logging.info("Removing {}".format(cache_fp))
        os.unlink(cache_fp)

    # Compress the FASTQ file
    logging.info("Compress the FASTQ file")
    run_cmds(["pigz", local_path])
    local_path = local_path + ".gz"

    # Return the path to the file
    logging.info("Done fetching " + accession)
    return local_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""Download a set of reads from SRA and save to an S3 bucket.""")

    parser.add_argument("--accession",
                        type=str,
                        required=True,
                        help="""SRA accession to download.""")
    parser.add_argument("--output-folder",
                        type=str,
                        required=True,
                        help="""S3 folder (key) to upload (interleaved) FASTQ.""")
    parser.add_argument("--temp-folder",
                        type=str,
                        default='/share',
                        help="Folder used for temporary files.")

    args = parser.parse_args()

    # If the output folder is not S3, make sure it exists locally
    if args.output_folder.startswith("s3://") is False:
        assert os.path.exists(args.output_folder), "Output folder does not exist"

    # Make sure the output folder ends with a "/"
    if args.output_folder.endswith("/") is False:
        args.output_folder = args.output_folder + "/"

    # Make a temporary folder for all files to be placed in
    temp_folder = os.path.join(args.temp_folder, str(uuid.uuid4())[:8])
    assert os.path.exists(temp_folder) is False
    os.mkdir(temp_folder)

    # Set up logging
    log_fp = os.path.join(temp_folder, args.accession + ".log")
    logFormatter = logging.Formatter(
        '%(asctime)s %(levelname)-8s [get_sra.py] %(message)s'
    )
    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.INFO)

    # Write to file
    fileHandler = logging.FileHandler(log_fp)
    fileHandler.setFormatter(logFormatter)
    rootLogger.addHandler(fileHandler)
    # Also write to STDOUT
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    rootLogger.addHandler(consoleHandler)

    # Set up the NCBI fastq-dump cache folder within the temp folder
    try:
        set_up_sra_cache_folder(temp_folder)
    except:
        exit_and_clean_up(temp_folder)

    # Download the SRA data
    try:
        local_fp = get_sra(args.accession, temp_folder)
    except:
        exit_and_clean_up(temp_folder)

    if args.output_folder.startswith("s3://"):
        # Upload FASTQ to S3 folder
        try:
            run_cmds(["aws", "s3", "cp", "--sse", "AES256",
                      local_fp, args.output_folder])
        except:
            exit_and_clean_up(temp_folder)

        # Upload logs to S3 folder
        try:
            run_cmds(["aws", "s3", "cp", "--sse",
                      "AES256", log_fp, args.output_folder])
        except:
            exit_and_clean_up(temp_folder)
    else:
        # Move FASTQ to local folder
        try:
            run_cmds(["mv", local_fp, args.output_folder])
        except:
            exit_and_clean_up(temp_folder)

        # Move logs to local folder
        try:
            run_cmds(["mv", log_fp, args.output_folder])
        except:
            exit_and_clean_up(temp_folder)
    
    # Delete any files that were created for this sample
    logging.info("Removing temporary folder: " + temp_folder)
    shutil.rmtree(temp_folder)
