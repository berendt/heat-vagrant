#!/bin/bash

sudo chsh -s /bin/bash ec2-user
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get upgrade -y
