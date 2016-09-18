# s3dt-catalog

This app allows to import a product catalog from [ED System](https://www.edsystem.cz/)
to [Shoptet](http://www.shoptet.cz/). In particular it converts the XML feed from one
format to another and allows for filtering and some additional transformations.

It is suited specifically for [Svět 3D tisku](http://eshop.svet-3d-tisku.cz) (3D Print World),
a Czech-based e-shop dedicated to 3D printing equipment.

## Requirements

See the `requirements.txt` file.

## About
- Author: [Bohumír Zámečník](http://bohumirzamecnik.cz) ([@bzamecnik](https://twitter.com/bzamecnik/))
- License: MIT

## Running locally

Edit `.env` to fill in the configuration (copy from `.env.example`).

Run:

```
honcho start
```

## Running as a Debian sysvinit service

### Installing

- put the repo to `/opt/s3dt_catalog`
- copy `init.d/s3dt_catalog` to `/etc/init.d/s3dt_catalog`
- `sudo useradd -r -s /bin/false s3dt_catalog`
- `mkdir /var/log`
- `chown -R s3dt_catalog:s3dt_catalog /opt/s3dt_catalog`


```
sudo service s3dt_catalog start
sudo service s3dt_catalog stop
sudo service s3dt_catalog restart
sudo service s3dt_catalog status
```
