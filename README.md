# Crawl Pantai

This is an example code crawling Pantai

## 🛠 Prerequisites

1.  **VPN Connection** You **must** be connected to the internal VPN before running this script. Pantai will not be reachable without an active secure tunnel.

2.  **Environment Configuration** Create a file named `.env` in the root directory of this project. Copy the template below and fill in your specific credentials:

    ```env
    DBHOST=localhost
    DBUSER=
    DBPASS=
    DBPORT=
    DBNAME=
    TABLE_NAME=
    SURVEY_PERIOD_ID=
    ```
    *Note: The `.env` file is ignored by Git to keep your credentials secure.*
3.  **Iteration File** The iteration.txt file that contain region level. The provided file is an example for level 4 Pantai region.

---

## 🚀 Execution

The script requires authentication credentials to be passed directly through the console.

### Running the Script
Open your terminal and run the command using your specific username and password:

```bash
python crawl_pantai.py