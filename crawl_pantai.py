import requests
import time
import pandas as pd
import re
import copy
import threading
import json
import os
import argparse

from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from login import login_with_sso
from dotenv import load_dotenv
from sqlalchemy import VARCHAR, DATETIME
from sqlalchemy import text

load_dotenv()


# ==============================
# CONFIG
# ==============================

BASE_URL = "https://fasih-sm.bps.go.id/analytic/api/v2/assignment/datatable-all-user-survey-periode"
LOGIN_URL = "https://fasih-sm.bps.go.id/"

REGION_FILE = "iteration.txt"
REGION_LIST_FILE = "region_list.csv"

OUTPUT_CSV = "fasih_data.csv"
COMPLETED_FILE = "completed_regions.txt"

COOKIE_FILE = "fasih_cookie.json"

PAGE_SIZE = 1000
MAX_WORKERS = 8
MAX_RETRIES = 5

BASE_DELAY = 0.7
RETRY_DELAY = 5

DBHOST=os.getenv("DBHOST")
DBUSER=os.getenv("DBUSER")
DBPASS=os.getenv("DBPASS")
DBPORT=os.getenv("DBPORT")
DBNAME=os.getenv("DBNAME")
TABLE_NAME=os.getenv("TABLE_NAME")
SURVEY_PERIOD_ID=os.getenv("SURVEY_PERIOD_ID")

COLUMN_TYPES = {
    "id": VARCHAR(150),
    "dateCreated": DATETIME(),
    "dateModified": DATETIME()
}
DATA_ASSIGNMENT = []


# ==============================
# DATABASE (SQLAlchemy)
# ==============================

engine = create_engine(
    f"mysql+pymysql://{DBUSER}:{DBPASS}@{DBHOST}:{DBPORT}/{DBNAME}",
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600
)

#DEFINE TABLE
DB_COLUMNS = [
"id","surveyPeriodId","mode","assignmentErrorStatusType",
"userIdResponsibility","approvedByCreator","codeIdentity",
"assignmentStatusId","assignmentStatusAlias","isTarikSample",

"data1","data2","data3","data4","data5",
"data6","data7","data8","data9","data10",

"dateCreated","isActive","sumError","sumRemark","sumClean",
"done","secondary","longitude","latitude","strata",
"externalDone","currentUserId","currentUserUsername",
"currentUserFullname","currentUserSurveyRoleId",
"currentUserSurveyRoleName","currentUserSurveyRoleIsPencacah",
"currentUserSurveyRoleCanPullSample","sourceFrom","listing",
"dateModified","assignmentResponsibility","assignmentResponsibilityAdmin",

"level1_code","level1_name",
"level2_code","level2_name",
"level3_code","level3_name",
"level4_code","level4_name",

"region","regionMetadata","sampleType","isTarget",
"referencedTo","lockedByUser","lockedByAnother"
]

# ==============================

session = requests.Session()

write_lock = threading.Lock()
progress_lock = threading.Lock()

header_written = False
header_columns = None

completed_regions = set()
progress_count = 0


# ==============================
# BASE PAYLOAD
# ==============================

BASE_PAYLOAD = {
    "draw":1,
    "columns":[
        {"data":"id"},
        {"data":"codeIdentity"},
        {"data":"data1"},
        {"data":"data2"},
        {"data":"data3"},
        {"data":"data4"},
        {"data":"data5"}
    ],
    "order":[{"column":0,"dir":"asc"}],
    "start":0,
    "length":PAGE_SIZE,
    "search":{"value":"","regex":False},
    "assignmentExtraParam":{
        "surveyPeriodId":SURVEY_PERIOD_ID,
        "assignmentErrorStatusType":-1,
        "filterTargetType":"TARGET_ONLY"
    }
}


# ==============================
# UTILITIES
# ==============================

def region_key(region):
    reg = ""
    for key in region.keys():
        reg = f"{reg},{region[key]}"
    return reg
    #return f"{region['region1Id']},{region['region2Id']},{region['region3Id']},{region['region4Id']}"


def convert_first_level(rows):

    cleaned = []

    for row in rows:

        new_row = {}

        for key,value in row.items():

            # normalize nested region JSON
            if key == "region" and isinstance(value, dict):

                l1 = value.get("level1")
                l2 = l1.get("level2") if isinstance(l1, dict) else None
                l3 = l2.get("level3") if isinstance(l2, dict) else None
                l4 = l3.get("level4") if isinstance(l3, dict) else None

                new_row["level1_code"] = l1.get("code") if l1 else None
                new_row["level1_name"] = l1.get("name") if l1 else None

                new_row["level2_code"] = l2.get("code") if l2 else None
                new_row["level2_name"] = l2.get("name") if l2 else None

                new_row["level3_code"] = l3.get("code") if l3 else None
                new_row["level3_name"] = l3.get("name") if l3 else None

                new_row["level4_code"] = l4.get("code") if l4 else None
                new_row["level4_name"] = l4.get("name") if l4 else None

                # keep original region JSON
                new_row["region"] = json.dumps(value,ensure_ascii=False)

            elif isinstance(value,(dict,list)):

                new_row[key] = json.dumps(value,ensure_ascii=False)

            else:

                new_row[key] = value

        cleaned.append(new_row)

    return cleaned


def enforce_schema(rows):

    fixed = []

    for row in rows:

        r = {}

        for col in DB_COLUMNS:
            r[col] = row.get(col, None)

        fixed.append(r)

    return fixed


# ==============================
# SAFE DB INSERT
# ==============================
def insert_to_array(df):
    global DATA_ASSIGNMENT
    DATA_ASSIGNMENT.append(df)

def insert_to_db(df):

    for attempt in range(1,4):

        try:

            df.to_sql(
                TABLE_NAME,
                engine,
                if_exists="replace",
                index=False,
                chunksize=1000,
                method="multi"
            )

            return

        except SQLAlchemyError as e:

            print("DB insert retry",attempt,e)

            time.sleep(2)

    print("FAILED DB INSERT")


# ==============================
# STORAGE
# ==============================

def append_to_storage(rows):

    rows = convert_first_level(rows)
    rows = enforce_schema(rows)

    df = pd.DataFrame(rows, columns=DB_COLUMNS)

    if "dateCreated" in df.columns:
        df["dateCreated"] = pd.to_datetime(df["dateCreated"], errors="coerce")

    if "dateModified" in df.columns:
        df["dateModified"] = pd.to_datetime(df["dateModified"], errors="coerce")

    # CSV
    with write_lock:
        file_exists = os.path.exists(OUTPUT_CSV)

        df.to_csv(
            OUTPUT_CSV,
            index=False,
            mode="a" if file_exists else "w",
            header=not file_exists
        )

        # ✅ ADD THIS (DB inside lock)
        insert_to_array(df)
        #insert_to_db(df)

# ==============================
# REQUEST RETRY
# ==============================

def request_with_retry(url,payload,headers):

    for attempt in range(1,MAX_RETRIES+1):

        try:

            r = session.post(
                url,
                json=payload,
                headers=headers,
                timeout=60
            )

            r.raise_for_status()

            return r.json()

        except Exception as e:

            print(f"Retry {attempt}/{MAX_RETRIES}",e)

            if attempt == MAX_RETRIES:
                raise

            time.sleep(RETRY_DELAY)


# ==============================
# REGION PARSER
# ==============================

def parse_iteration_file(filepath):

    with open(filepath,"r",encoding="utf8") as f:
        text = f.read()

    region1 = re.search(r'"id":\s*"([^"]+)"',text).group(1)

    level2 = re.search(r'Level 2:(.*?)Level 3:',text,re.S).group(1)

    region2 = {}

    for m in re.finditer(r'"id":\s*"([^"]+)".*?"fullCode":\s*"([^"]+)"',level2,re.S):

        rid,code = m.groups()

        region2[code] = rid


    region3 = {}

    lvl3 = re.findall(r'([A-Z0-9]+)\s*=>\s*\{.*?"data":\s*\[(.*?)\]',text,re.S)

    for parent,data in lvl3:

        items = re.findall(r'"id":\s*"([^"]+)".*?"fullCode":\s*"([^"]+)"',data,re.S)

        region3[parent] = [{"id":i,"code":c} for i,c in items]


    region4 = {}

    lvl4_text = text.split("Level 4:")[1]

    lvl4 = re.findall(r'([A-Z0-9]+)\s*=>\s*\{.*?"data":\s*\[(.*?)\]',lvl4_text,re.S)

    for parent,data in lvl4:

        ids = re.findall(r'"id":\s*"([^"]+)"',data)

        region4[parent] = ids


    combos = []

    for r2_code,r2_id in region2.items():

        for r3 in region3.get(r2_code,[]):

            r3_id = r3["id"]
            r3_code = r3["code"]

            for r4_id in region4.get(r3_code,[]):

                combos.append({
                    "region1Id":region1,
                    "region2Id":r2_id,
                    "region3Id":r3_id,
                    "region4Id":r4_id
                })

    return combos

def load_or_create_region_list():

    if os.path.exists(REGION_LIST_FILE):

        print("Loading region list from CSV...")

        df = pd.read_csv(REGION_LIST_FILE)

        regions = df.to_dict(orient="records")

        return regions

    print("region_list.csv not found, parsing iteration file...")

    regions = parse_iteration_file(REGION_FILE)

    df = pd.DataFrame(regions)

    df.to_csv(REGION_LIST_FILE,index=False)

    print("Region list saved to region_list.csv")

    return regions

# ==============================
# COMPLETED TRACKER
# ==============================

def load_completed():

    if not os.path.exists(COMPLETED_FILE):
        return set()

    with open(COMPLETED_FILE) as f:
        return set(line.strip() for line in f)


def save_completed(key):

    with write_lock:

        with open(COMPLETED_FILE,"a") as f:
            f.write(key+"\n")


# ==============================
# SCRAPE REGION
# ==============================

def scrape_region(region,index,total,headers):

    global progress_count

    key = region_key(region)

    if key in completed_regions:
        print(f"Region {index}/{total} skipped")
        return

    start_row = 0
    draw = 1

    while True:

        payload = copy.deepcopy(BASE_PAYLOAD)

        payload["start"] = start_row
        payload["draw"] = draw

        payload["assignmentExtraParam"].update(region)

        res = request_with_retry(BASE_URL,payload,headers)

        batch = res.get("searchData",[])

        if not batch:
            break

        append_to_storage(batch)

        print(f"Region {index}/{total} - batch {len(batch)}")

        start_row += PAGE_SIZE
        draw += 1

        time.sleep(BASE_DELAY)

    save_completed(key)

    with progress_lock:

        progress_count += 1
        print(f"Completed {progress_count}/{total}")

# ==============================
# COOKIE CHECK
# ==============================

def save_cookie(cookies):

    with open(COOKIE_FILE,"w",encoding="utf8") as f:
        json.dump(cookies,f)

    print("Cookie saved")


def load_cookie():

    if not os.path.exists(COOKIE_FILE):
        return None

    with open(COOKIE_FILE,"r",encoding="utf8") as f:
        cookies = json.load(f)

    print("Cookie loaded")

    return cookies


def cookie_to_header(cookies):

    cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

    xsrf_token = next((c['value'] for c in cookies if c['name']=="XSRF-TOKEN"),None)

    headers = {
        "Accept":"application/json",
        "Content-Type":"application/json",
        "User-Agent":"Mozilla/5.0",
        "X-XSRF-TOKEN":xsrf_token.replace('%3D','=') if xsrf_token else "",
        "Cookie":cookie_string,
        "Origin":"https://fasih-sm.bps.go.id",
        "Referer":"https://fasih-sm.bps.go.id/"
    }

    return headers


def test_cookie(headers):

    payload = copy.deepcopy(BASE_PAYLOAD)
    payload["length"] = 1

    try:

        r = session.post(
            BASE_URL,
            json=payload,
            headers=headers,
            timeout=20
        )

        if r.status_code == 200:
            print("Cookie still valid")
            return True

    except Exception:
        pass

    print("Cookie expired")

    return False
	
# ==============================
# MAIN
# ==============================


def main():

    global completed_regions

    # ==============================
    # ARGUMENTS
    # ==============================
    parser = argparse.ArgumentParser()

    parser.add_argument("user")
    parser.add_argument("password")
    parser.add_argument("otp", nargs="?", default=None)

    args = parser.parse_args()

    username = args.user
    password = args.password
    otp = args.otp

    # ==============================
    # COOKIE HANDLING FIRST
    # ==============================

    cookies = load_cookie()

    if cookies:

        headers = cookie_to_header(cookies)

        if not test_cookie(headers):
            cookies = None

    if not cookies:

        page,browser = login_with_sso(username,password,otp)

        if not page:
            print("Login gagal")
            return

        page.goto(LOGIN_URL)
        page.wait_for_load_state("networkidle")

        cookies = page.context.cookies()

        save_cookie(cookies)

        browser.close()

        headers = cookie_to_header(cookies)

        print("Login berhasil")

    else:

        headers = cookie_to_header(cookies)

        print("Using saved cookie")

    # ==============================
    # AFTER COOKIE READY:
    # CHECK FRESH START / RESUME
    # ==============================

    fresh_start = not os.path.exists(COMPLETED_FILE)

    if fresh_start:
        print("Fresh start detected → clearing table")

        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {TABLE_NAME}"))

    else:
        print("Resume mode → continue scraping")

    # ==============================
    # REGION + PROGRESS
    # ==============================

    regions = load_or_create_region_list()

    total = len(regions)

    completed_regions = load_completed()

    print("Total region:",total)
    print("Already completed:",len(completed_regions))

    # ==============================
    # MULTITHREAD SCRAPING
    # ==============================

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

        futures = []

        for i,r in enumerate(regions,1):
            print(r)
            futures.append(
                executor.submit(scrape_region,r,i,total,headers)
            )

        for f in as_completed(futures):

            try:
                f.result()
            except Exception as e:
                print("Region error:",e)

    print("Scraping selesai")

    # ==============================
    # WRITE TO DB (AFTER ALL SCRAPING DONE)
    # ==============================
    dt_all = pd.concat(DATA_ASSIGNMENT, ignore_index=True)
    insert_to_db(dt_all)

    # ==============================
    # CLEANUP
    # ==============================

    if os.path.exists(COMPLETED_FILE):
        os.remove(COMPLETED_FILE)
        print("completed_regions.txt deleted (all regions finished)")

if __name__ == "__main__":
    main()