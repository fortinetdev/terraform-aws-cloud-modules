import os
import logging
import time
import base64
import urllib
import requests
import re

class FgtConf:
    def __init__(self):
        self.logger = logging.getLogger("lambda")
        self.logger.setLevel(logging.INFO)
        self.cookie = {}
        self.fgt_password = os.getenv("fgt_password")
        self.fgt_login_port = ""
        self.return_json = {
            'StatusCode': 200,
            'FunctionError': None,
            'Payload': None
        }

    def main(self, event):
        self.logger.info(f"Start internal lambda function.")
        self.fgt_private_ip = event["private_ip"]
        operation = event["operation"]
        parameters = event["parameters"]
        if operation == "change_password":
            if "fgt_vm_id" not in parameters:
                self.return_json['StatusCode'] = 500
                self.return_json['FunctionError'] = "Could not find parameter fgt_vm_id."
                return
            b_succ = self.change_password(parameters["fgt_vm_id"])
            if not b_succ:
                self.return_json['StatusCode'] = 500
                self.return_json['FunctionError'] = "Could not change password."
                return
        elif operation == "upload_license":
            if "license_type" not in parameters or "license_content" not in parameters:
                self.return_json['StatusCode'] = 500
                self.return_json['FunctionError'] = "Missing one of the parameters: license_type, license_content."
                return
            b_succ = self.upload_license(parameters["license_type"], parameters["license_content"])
            if not b_succ:
                self.return_json['StatusCode'] = 500
                self.return_json['FunctionError'] = "Could not upload license."
                return
        elif operation == "upload_config":
            if "config_content" not in parameters:
                self.return_json['StatusCode'] = 500
                self.return_json['FunctionError'] = "Could not find parameter config_content."
                return
            b_succ = self.upload_config(parameters["config_content"])
            if not b_succ:
                self.return_json['StatusCode'] = 500
                self.return_json['FunctionError'] = "Could not cupload configuration to FortiGate instance."
                return
        else:
            self.return_json['StatusCode'] = 500
            self.return_json['FunctionError'] = f"Unknown operation {operation}."
            return

    
# License
    def upload_license(self, license_type, license_content):
        self.logger.info(f"Upload license to FortiGate instance.")
        # Upload license
        b_connected = self.connect_to_fgt_http()
        if not b_connected:
            self.logger.error(f"Could not http connect to FortiGate {self.fgt_private_ip}")
            self.return_json['StatusCode'] = 500
            self.return_json['FunctionError'] = f"Could not http connect to FortiGate {self.fgt_private_ip}"
            return False
        if license_type == "token":
            b_succ = self.upload_license_token_http(license_content)
            if not b_succ:
                self.return_json['StatusCode'] = 500
                self.return_json['FunctionError'] = "Active license token on FortiGate instance failed."
                return

        elif license_type == "file":
            b_succ = self.upload_license_file_http(license_content)
            if not b_succ:
                self.return_json['StatusCode'] = 500
                self.return_json['FunctionError'] = "Upload license file to FortiGate instance failed."
                return
        return True

    def upload_license_token_http(self, lic_token):
        self.logger.info("Active license token by HTTP.")
        url = f"https://{self.fgt_private_ip}{self.fgt_login_port}/api/v2/monitor/system/vmlicense/download?&token={lic_token}"

        header = {
            "Content-Type": "application/json",
            "Cookie": self.cookie["cookie"],
            "X-CSRFTOKEN": self.cookie["csrftoken"]
        }
        response = requests.post(url, headers=header, verify=False, timeout=20)
        fgt_return_status = False
        if response.status_code == 200:
            response_json = response.json()
            https_status = 0
            if response_json:
                https_status = response_json['http_status']
                if https_status == 200:
                    fgt_return_status = True
            else:
                self.logger.info("Could not get http return status")

        response.close()
        return fgt_return_status

    def upload_license_file_http(self, lic_file_content):
        self.logger.info("Active license token by HTTP.")
        url = f"https://{self.fgt_private_ip}{self.fgt_login_port}/api/v2/monitor/system/vmlicense/upload"
        header = {
            "Content-Type": "application/json",
            "Cookie": self.cookie["cookie"],
            "X-CSRFTOKEN": self.cookie["csrftoken"]
        }
        b64_encode_lic = base64.b64encode(lic_file_content.encode("ascii")).decode("ascii")
        body = {
            "file_content" : b64_encode_lic
        }
        response = requests.post(url, headers=header, json=body, verify=False, timeout=20)
        fgt_return_status = False
        if response.status_code == 200:
            response_json = response.json()
            https_status = 0
            if response_json:
                https_status = response_json['http_status']
                if https_status == 200:
                    fgt_return_status = True
            else:
                self.logger.info("Could not get http return status")
        response.close()
        return fgt_return_status

# FortiGate configuration
    def upload_config(self, config_content):
        self.logger.info("Upload configuration file by HTTP.")
        b_connected = self.connect_to_fgt_http(check_get=True)
        if not b_connected:
            self.logger.error(f"Could not http connect to FortiGate {self.fgt_private_ip}")
            self.return_json['StatusCode'] = 500
            self.return_json['FunctionError'] = f"Could not http connect to FortiGate {self.fgt_private_ip}"
            return False
        url = f"https://{self.fgt_private_ip}{self.fgt_login_port}/api/v2/monitor/system/config-script/upload"
        header = {
            "Content-Type": "application/json",
            "Cookie": self.cookie["cookie"],
            "X-CSRFTOKEN": self.cookie["csrftoken"]
        }
        b64_encode_lic = base64.b64encode(config_content.encode("ascii")).decode("ascii")
        body = {
            "filename": "config_lambda",
            "file_content" : b64_encode_lic
        }
        response = requests.post(url, headers=header, json=body, verify=False, timeout=20)
        fgt_return_status = False
        if response.status_code == 200:
            response_json = response.json()
            https_status = 0
            if response_json:
                https_status = response_json['http_status']
                if https_status == 200:
                    fgt_return_status = True
            else:
                self.logger.info("Could not get http return status")
        response.close()
        return fgt_return_status

# using http
    def connect_to_fgt_http(self, check_get=False, max_loop=10):
        self.logger.info("Check connection to FortiGate instance.")
        fgt_login_port_number = os.getenv("fgt_login_port_number")
        login_succ = False
        encoded_fgt_password = urllib.parse.quote(self.fgt_password)
        port = ""
        for i in range(max_loop):
            if i > 0 and port == "":
                self.logger.info(f"Sleep {i} 30 sec.")
                time.sleep(30)
            url = f"https://{self.fgt_private_ip}{port}/logincheck?username=admin&secretkey={encoded_fgt_password}"
            header = {
                "Content-Type": "application/json"
            }
            try:
                response = requests.post(url, headers=header, verify=False, timeout=20)
                if response.status_code == 200:
                    self.cookie["cookie"] = ""
                    self.cookie["csrftoken"] = ""
                    login_succ = False
                    for k, v in response.headers.items():
                        if k.lower() == "set-cookie":
                            cookie_list = v.split(',')
                            cookie_list = [ ele.split(';')[0] for ele in cookie_list]
                            for item in cookie_list:
                                cur_v = item.strip()
                                if "ccsrftoken" in cur_v:
                                    csrftoken = re.search('\"(.*)\"', cur_v)
                                    if csrftoken and csrftoken.group(1) != "0%260":
                                        self.cookie["csrftoken"] = csrftoken.group(1)
                                        self.cookie["cookie"] = ";/n".join(cookie_list)
                                        login_succ = True
                            if login_succ:
                                break
                    if login_succ and check_get:
                        login_succ = self.check_get_http(port)
                else:
                    self.logger.info("Could not get http return status")
                # response.close()
                if login_succ:
                    self.fgt_login_port = port
                    break
            except Exception as err:
                self.logger.info(f"Could not get http return status, try again. Error: {err}")
            if port == "" and fgt_login_port_number != "":
                port = ":" + fgt_login_port_number
            else:
                port = ""
        return login_succ

    def change_password(self, fgt_vm_id):
        self.logger.info("Change password for FortiGate instance.")
        b_succ = False
        
        session_key = ""
        max_loop = 10
        for i in range(max_loop):
            url = f"https://{self.fgt_private_ip}/api/v2/authentication"
            header = {
                "Content-Type": "application/json"
            }
            body = {
                "username" : "admin",
                "secretkey" : f"{fgt_vm_id}",
                "ack_pre_disclaimer" : True,
                "ack_post_disclaimer" : True,
                "new_password1" : f"{self.fgt_password}",
                "new_password2" : f"{self.fgt_password}",
                "request_key": True
            }
            try:
                response = requests.post(url, headers=header, json=body, verify=False, timeout=20)
                if response.status_code == 200:
                    response_json = response.json()
                    status_code = 0
                    if response_json:
                        status_code = response_json['status_code']
                        if status_code == 5:
                            b_succ = True
                            session_key = response_json['session_key']
                        else:
                            self.logger.info(f"Status code is not 5, but {status_code}")
                    else:
                        self.logger.info("Could not get http status_code")
                else:
                    self.logger.info("Could not get http return status")
                response.close()
                if b_succ:
                    break
            except Exception as err:
                self.logger.info(f"Could not get http return status, try again. Error: {err}")
            b_succ = self.connect_to_fgt_http(max_loop=1)
            if b_succ:
                break
            self.logger.info(f"Sleep {i} 30 sec.")
            time.sleep(30)
        if b_succ:
            # Logout
            url = f"https://{self.fgt_private_ip}/api/v2/authentication"
            header = {
                "Content-Type": "application/json"
            }
            body = {
                "session_key": f"{session_key}"
            }
            try:
                response = requests.post(url, headers=header, json=body, verify=False, timeout=20)
            except Exception as err:
                self.logger.info(f"Logout exception. Error: {err}")
            response.close()
        
        return b_succ

    def check_get_http(self, port=""):
        self.logger.info("Check get system status.")
        url = f"https://{self.fgt_private_ip}{port}/api/v2/monitor/system/status"
        header = {
            "Content-Type": "application/json",
            "Cookie": self.cookie["cookie"],
            "X-CSRFTOKEN": self.cookie["csrftoken"]
        }
        fgt_return_status = False
        try:
            response = requests.get(url, headers=header, verify=False, timeout=30)
            if response.status_code == 200:
                response_json = response.json()
                if response_json:
                    status = response_json['status']
                    if status == "success":
                        fgt_return_status = True
                else:
                    self.logger.info("Could not get http return status")
            response.close()
        except Exception as err:
            self.logger.info(f"Could not get http return status, try again. Error {err}")
        return fgt_return_status

 
def lambda_handler(event, context):
    ## FortiGate configuration operations
    fgtObject = FgtConf()
    fgtObject.main(event)

    return fgtObject.return_json