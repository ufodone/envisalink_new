#!/bin/bash

src_dir=$1
dst_dir=$2

if [ -d $src_dir ]; then
    cp -R $src_dir/* $dst_dir
    cd $dir_dir
    git add .
    git commit -m "Sync wiki changes"
    git push
fi
