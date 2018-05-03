FROM ubuntu:16.04
MAINTAINER sminot@fredhutch.org

# Use /share as the working directory
RUN mkdir /share
WORKDIR /share

# Add /scratch
RUN mkdir /scratch

# Install prerequisites
RUN apt update && \
    apt-get install -y build-essential wget unzip python3 awscli pigz git

# Set the default langage to C
ENV LC_ALL C

# Install the SRA toolkit
RUN cd /usr/local/bin && \
    wget -q https://ftp-trace.ncbi.nlm.nih.gov/sra/sdk/2.8.2/sratoolkit.2.8.2-ubuntu64.tar.gz && \
    tar xzf sratoolkit.2.8.2-ubuntu64.tar.gz && \
    ln -s /usr/local/bin/sratoolkit.2.8.2-ubuntu64/bin/* /usr/local/bin/ && \
    rm sratoolkit.2.8.2-ubuntu64.tar.gz

# Install CMake3.11
RUN cd /usr/local/bin && \
    wget https://cmake.org/files/v3.11/cmake-3.11.0-Linux-x86_64.tar.gz && \
    tar xzvf cmake-3.11.0-Linux-x86_64.tar.gz && \
    ln -s $PWD/cmake-3.11.0-Linux-x86_64/bin/cmake /usr/local/bin/

# Install fastq-pair
RUN cd /usr/local && \
    git clone https://github.com/linsalrob/fastq-pair.git && \
    cd fastq-pair && \
    git checkout 4ae91b0d9074410753d376e5adfb2ddd090f7d85 && \
    mkdir build && \
    cd build && \
    cmake ../ && \
    make && \
    make install

# Add the run script to the PATH
ADD get_sra.py /usr/local/bin/

# scliluig-containertask prereqs
RUN mkdir /mnt/inputs && mkdir /mnt/outputs
RUN apt-get install -y python3-pip
RUN ln -s /usr/bin/python3 /usr/bin/python
RUN pip3 install bucket_command_wrapper==0.2.0 
