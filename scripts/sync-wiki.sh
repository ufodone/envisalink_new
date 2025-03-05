#!/bin/bash

src_dir=$1
dst_dir=$2

echo "PWD:$(pwd)"

echo "src:"
ls -la $src_dir
echo "dst:"
ls -la $dst_dir

if [ -d $src_dir ]; then
    cp -R $src_dir/* $dst_dir
    cd $dst_dir
    git add .
    git commit -m "Sync wiki changes"
    git push
fi
