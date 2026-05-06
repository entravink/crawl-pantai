# Crawl Pantai

This is an example code for crawling Pantai

## 🛠 Prerequisites

1.  **VPN Connection** You **must** be connected to the internal VPN before running this script. Pantai will not be reachable without an active secure tunnel.

2.  **Environment Configuration** Create a file named `.env` in the root directory of this project. Copy the template below and fill in your specific credentials:

    ```env
    DBHOST=
    DBUSER=
    DBPASS=
    DBPORT=
    DBNAME=
    TABLE_NAME=
    SURVEY_PERIOD_ID=d63e9832-13c6-4ec7-bf5b-59229c2f90f9
    ```
    *Note: The `.env` file is ignored by Git to keep your credentials secure.*
3.  **Iteration File** The iteration.txt file that contain region level. The provided file is an example for level 4 Pantai region. Iteration file can define manualy or running by script bellow:
```bash
    # running get iteration
    py getRegion.py username password survei_id code_region

    # for example
    py getRegion.py username password 345cbe9e-45b8-42c2-bc4a-c76fe52a97ea 51
```
choose file in folder interation_files and move to / and then changes name into region_list.csv

4.  **Playwright & Dependencies:** Install the Python package and the necessary browser engines:
    ```bash
    # Install the library
    pip install playwright

    # Install the required browsers (Chromium, Firefox, etc.)
    playwright install
    ```

---

## 🚀 Execution

The script requires authentication credentials to be passed directly through the console.

### Running the Script
Open your terminal and run the command using your specific username and password:

```bash
python crawl_pantai.py