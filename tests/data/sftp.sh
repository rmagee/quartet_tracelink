#!/usr/bin/env bash
mkdir /tmp/upload;
chmod 777 /tmp/upload;
docker run -v /tmp/upload:/home/foo/upload -p 2222:22 -d atmoz/sftp foo:pass:1001
