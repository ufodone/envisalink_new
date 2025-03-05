#!/bin/bash

base_repo_dir=$1
src_wiki_dir=$base_repo_dir/wiki
wiki_depo_dir=$2

if [ -d $src_wiki_dir]; then
    cp -R $src_wiki_dir/* $wiki_depo_dir
    cd $wiki_depo_dir
    git config --global user.name "$GITHUB_ACTOR"
    git config --global user.email "$GITHUB_ACTOR@users.noreply.github.com"
    git add .
    git commit -m "Sync wiki changes"
    git push
fi
