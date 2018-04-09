FROM ubuntu:16.04
MAINTAINER sminot@fredhutch.org

# Use /share as the working directory
RUN mkdir /share
WORKDIR /share

# Install prerequisites
RUN apt update && \
    apt-get install -y build-essential wget unzip python2.7 \
    python-dev git python-pip awscli pigz

# Set the default langage to C
ENV LC_ALL C

# Install the SRA toolkit
RUN cd /usr/local/bin && \
    wget -q https://ftp-trace.ncbi.nlm.nih.gov/sra/sdk/2.8.2/sratoolkit.2.8.2-ubuntu64.tar.gz && \
    tar xzf sratoolkit.2.8.2-ubuntu64.tar.gz && \
    ln -s /usr/local/bin/sratoolkit.2.8.2-ubuntu64/bin/* /usr/local/bin/ && \
    rm sratoolkit.2.8.2-ubuntu64.tar.gz

# Add the run script to the PATH
ADD get_sra.py /usr/local/bin/
