# vendor/

Extracted `py3-none-any` wheel trees for `easy-cheese-schemas`' runtime
dependencies. Committed rather than downloaded at build time so
`build-pyz.yml`'s rebuild-and-byte-compare stays hermetic.

| Package | Version |
| --- | --- |
| attrs | 26.1.0 |
| cattrs | 26.1.0 |
| typing_extensions | 4.16.0 |

All three are pure Python — `zipimport` cannot load native extensions from
inside a zipapp, which is why attrs + cattrs were chosen over pydantic.

To refresh, download the wheels with `--only-binary=:all: --python-version 3.11`
and extract every member except the `.dist-info/` directories into this tree.
