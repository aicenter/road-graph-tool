# Performance of importing on local machine
## Hardware configuration
- **System**: Linux
- **Version**: #40~22.04.3-Ubuntu SMP PREEMPT_DYNAMIC Tue Jul 30 17:30:19 UTC 2
- **Logical cores**: 8
- **Total memory**: 16.54 GB
- **Total disk space**: 502.39 GB
- **osm2pgsql version**: 1.11.0

## Database information with performance

**Local database - wireless connection:**
- 14.12 (Ubuntu 14.12-0ubuntu0.22.04.1)

| Location | File size | Date of import | Speed of import | Nodes size | Ways size | Relations size |
| --- | --- | --- | --- | --- | --- | --- |
| Czechia | 860.05 MB | 19.08.2024 | 32min | 11 GB | 5285 MB | 106 MB |
| Germany | 4.33 GB | 20.08.2024 | 2h 39min | 49 GB | 31 GB | 504 MB |

**Remote database - ethernet connection:**
- PostgreSQL 16.1 (Debian 16.1-1.pgdg110+1)

| Location | File size | Date of import | Speed of import | Nodes size | Ways size | Relations size |
| --- | --- | --- | --- | --- | --- | --- |
| Czechia | 860.05 MB | 21.08.2024 | 32min | 11 GB | 5285 MB | 107 MB |
| Germany | 4.33 GB | 2.09.2024 | 2h 38min | 49 GB | 31 GB | 504 MB |


# Performance of importing on server
## Hardware configuration
- **System**: Linux
- **Version**: #1 SMP Debian 4.19.181-1 (2021-03-19)
- **Logical cores**: 32
- **Total memory**: 179.59 GB GB
- **Total disk space**: 1837.91 GB GB
- **osm2pgsql version**: 1.8.0

## Database information with performance

**Remote database - ethernet connection:**
- PostgreSQL 16.1 (Debian 16.1-1.pgdg110+1)

| Location | File size | Date of import | Speed of import | Nodes size | Ways size | Relations size |
| --- | --- | --- | --- | --- | --- | --- |
| Czechia | 860.05 MB | 19.09.2024 | 32min | 11 GB | 107 MB | 4916 MB |
| Germany | 4.33 GB | 19.09.2024 | 2h 34min | 47 GB | 28 GB | 509 MB |