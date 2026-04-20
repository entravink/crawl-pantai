from playwright.sync_api import sync_playwright
import getpass
import sys
import json
import requests
import pandas as pd
from tqdm import tqdm

def main():
    try:
        #username = input("Username: ")
        #password = getpass.getpass("Password: ")
        username = sys.argv[1]
        password = sys.argv[2]
        survei_id = sys.argv[3]
        code_region_1 = sys.argv[4]

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            print("Membuka halaman login...")
            page.goto("https://fasih-sm.bps.go.id/oauth_login.html", timeout=60000)

            # Klik tombol SSO
            print("Klik Login SSO BPS...")
            page.click("a.login-button")

            # Tunggu halaman SSO muncul
            page.wait_for_selector("#username", timeout=60000)

            # Isi form login
            print("Mengisi username & password...")
            page.fill("#username", username)
            page.fill("#password", password)

            # Submit login
            print("Submit login...")
            page.click("#kc-login")

            # Tunggu redirect setelah login
            page.wait_for_load_state("networkidle", timeout=60000)

            print("Login selesai (cek apakah berhasil di browser).")


            # ambil cookies dari browser
            cookies_list = context.cookies()

            # convert ke format requests
            cookies = {c["name"]: c["value"] for c in cookies_list}

            # request pakai session yang sama
            url = f"https://fasih-sm.bps.go.id/survey/api/v1/surveys/{survei_id}"
            response = context.request.get(url)
            try:
                data = response.json()
                groupId=data['data']['regionGroupId']
                surveyTemplate=data['data']['surveyTemplates'][0]['templateId']
                surveyPeriod=data['data']['surveyPeriods'][0]['id']
                is_update_listing=data['data']['updateListingType']
                url = f"https://fasih-sm.bps.go.id/region/api/v1/region-metadata?id={groupId}"
                response = context.request.get(url, timeout=60000)
                try:
                    data = response.json()
                    region_level_count=data['data']['levelCount']
                    region_level=data['data']['level']
                    region_meta={}
                    kode_level_1 = ''
                    for reg in tqdm(region_level):
                        if reg['id']==1:
                            url = f'https://fasih-sm.bps.go.id/region/api/v1/region/level1?groupId={groupId}&level1FullCode=51'
                            response = context.request.get(url, timeout=60000)
                            try:
                                data = response.json()
                                for j in data['data']:
                                    if j['fullCode']==code_region_1:
                                        dt = pd.json_normalize({"region1Id":j['id'],"region1FullCode":j['fullCode'],"region1Name":j['name'],"region1Code":j['code']})
                                        kode_level_1 = j['fullCode']
                                        region_meta['region'+str(reg['id'])]=dt
                                        #pilih hanya ['region1Id']
                                        dt = dt[['region1Id']]
                                        dt.to_csv(f"iteration_files/region_list_{reg['id']}.csv",index=False)
                                        break
                            except Exception as e:
                                print("Error parsing JSON REGION LEVEL 1 : " + url + ":")
                                print(e)
                        else:
                            reg_bef=region_meta['region'+str(reg['id']-1)]
                            dt_all = []
                            for _, rb in reg_bef.iterrows():
                                parent_id = rb['region'+str(reg['id']-1)+'Id']
                                url = f'https://fasih-sm.bps.go.id/region/api/v1/region/level{reg["id"]}?groupId={groupId}&level{reg["id"]-1}Id={parent_id}'
                                response = context.request.get(url,timeout=60000)
                                try:
                                    data = response.json()
                                    dt = pd.json_normalize(data['data'])
                                    dt = dt.rename(columns={
                                        'id': f'region{reg["id"]}Id',
                                        'fullCode': f'region{reg["id"]}FullCode',
                                        'code': f'region{reg["id"]}Code',
                                        'name': f'region{reg["id"]}Name'
                                    })
                                    dt_sebelum = reg_bef[
                                        reg_bef[f'region{reg["id"]-1}Id'] == parent_id
                                    ]
                                    dt = dt_sebelum.merge(dt, how='cross')
                                    dt_all.append(dt)
                                
                                except Exception as e:
                                    print(f"Error parsing JSON REGION LEVEL {reg['id']} : {url}")
                                    print(e)
                            dt_all_concat = pd.concat(dt_all, ignore_index=True)
                            # simpan ID saja
                            region_meta[f'region{reg["id"]}'] = dt_all_concat
                            for i in range(1, reg['id']+1):
                                dt_all_concat = dt_all_concat.drop(columns=[f'region{i}Code',f'region{i}FullCode', f'region{i}Name'])
                            dt_all_concat.to_csv(f"iteration_files/region_list_{reg['id']}.csv", index=False)
                            
                except Exception as e:
                    print("Error parsing JSON REGION LEVEL : " + url + ":")
                    print(e)
            except Exception as e:
                print("Error parsing JSON Get Survei ID : " + url + ":")
                print(e)
            # Optional: tahan browser supaya tidak langsung close
            input("Tekan ENTER untuk menutup browser...")
            browser.close()

    except Exception as e:
        print("Terjadi error:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()