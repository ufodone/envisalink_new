#!/bin/bash

src_dir=$1
dst_dir=$2

if [ -d $src_dir ]; then
    cp -R $src_dir/* $dst_dir
    cd $dst_dir
    git config --global user.name "David O'Neill"
    git config --global user.email "ufodone@gmail.com"
    git add .
    git commit -m "Sync wiki changes"
    git push
fi
