import os
import logging
import time
import base64
import urllib
import requests
import re
import boto3
import botocore
from botocore.exceptions import ClientError

class Helper:
    def check_missed_var(required_var_list, target_input):
        missed_var_list = []
        for v in required_var_list:
            if v not in target_input:
                missed_var_list.append(v)
        return missed_var_list


class FgtConf:
    def __init__(self):
        self.logger = logging.getLogger("lambda")
        self.logger.setLevel(logging.INFO)
        self.cookie = {}
        self.fgt_password = os.getenv("fgt_password")
        self.fgt_login_port = "" if os.getenv("fgt_login_port_number") == "" else ":" + os.getenv("fgt_login_port_number")
        self.return_json = {
            'ErrorMsg': None,
            'ResponseContent': None
        }

    def main(self, event):
        self.logger.info(f"Start internal lambda function for FortiOS configuration service.")
        operation = event["operation"]
        parameters = event["parameters"]
        if "private_ip" not in parameters:
            self.return_json['ErrorMsg'] = "Could not find parameter private_ip."
            return
        self.fgt_private_ip = parameters["private_ip"]
        if operation == "change_password":
            if "fgt_vm_id" not in parameters:
                self.return_json['ErrorMsg'] = "Could not find parameter fgt_vm_id."
                return
            b_succ = self.change_password(parameters["fgt_vm_id"])
            if not b_succ:
                self.return_json['ErrorMsg'] = "Could not change password."
                return
        elif operation == "upload_license":
            missed_var_list = Helper.check_missed_var(["license_type", "license_content"], parameters)
            if missed_var_list:
                self.return_json['ErrorMsg'] = "Could not find parameter: " + ", ".join(missed_var_list) + "."
                return
            b_succ = self.upload_license(parameters["license_type"], parameters["license_content"])
            if not b_succ:
                self.return_json['ErrorMsg'] = "Could not upload license."
                return
        elif operation == "upload_config":
            if "config_content" not in parameters:
                self.return_json['ErrorMsg'] = "Could not find parameter config_content."
                return
            b_succ = self.upload_config(parameters["config_content"])
            if not b_succ:
                self.return_json['ErrorMsg'] = "Could not cupload configuration to FortiGate instance."
                return
        else:
            self.return_json['ErrorMsg'] = f"Unknown operation {operation}."
            return

    
 # License
    def upload_license(self, license_type, license_content):
        self.logger.info(f"Upload license to FortiGate instance.")
        # Upload license
        b_connected = self.connect_to_fgt_http()
        if not b_connected:
            self.logger.error(f"Could not http connect to FortiGate {self.fgt_private_ip}")
            self.return_json['ErrorMsg'] = f"Could not http connect to FortiGate {self.fgt_private_ip}"
            return False
        if license_type == "token":
            b_succ = self.upload_license_token_http(license_content)
            if not b_succ:
                self.return_json['ErrorMsg'] = "Active license token on FortiGate instance failed."
                return

        elif license_type == "file":
            b_succ = self.upload_license_file_http(license_content)
            if not b_succ:
                self.return_json['ErrorMsg'] = "Upload license file to FortiGate instance failed."
                return
        return True

    def upload_license_token_http(self, lic_token):
        self.logger.info("Active license token by HTTP.")
        url = f"https://{self.fgt_private_ip}{self.fgt_login_port}/api/v2/monitor/system/vmlicense/download"

        header = {
            "Content-Type": "application/json",
            "Cookie": self.cookie["cookie"],
            "X-CSRFTOKEN": self.cookie["csrftoken"]
        }
        body = {
            "token" : lic_token
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
            self.return_json['ErrorMsg'] = f"Could not http connect to FortiGate {self.fgt_private_ip}"
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
    def connect_to_fgt_http(self, check_get=False, max_loop=10, fgt_password=""):
        self.logger.info("Check connection to FortiGate instance.")
        if not fgt_password:
            fgt_password = self.fgt_password
        login_succ = False
        encoded_fgt_password = urllib.parse.quote(fgt_password)
        for i in range(max_loop):
            if i > 0:
                self.logger.info(f"Sleep {i} 30 sec.")
                time.sleep(30)
            url = f"https://{self.fgt_private_ip}{self.fgt_login_port}/logincheck?username=admin&secretkey={encoded_fgt_password}"
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
                        login_succ = self.check_get_http()
                else:
                    self.logger.info("Could not get http return status")
                # response.close()
                if login_succ:
                    break
            except Exception as err:
                self.logger.info(f"Could not get http return status, try again. Error: {err}")
        return login_succ

    def change_password(self, fgt_vm_id):
        self.logger.info("Change password for FortiGate instance.")
        b_succ = False
        
        session_key = ""
        max_loop = 10
        for i in range(max_loop):
            api = ""
            if i % 2:
                api = "authentication"
                url = f"https://{self.fgt_private_ip}{self.fgt_login_port}/api/v2/authentication"
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
                params = None
            else:
                api = "loginpwd_change"
                b_succ_login = self.connect_to_fgt_http(fgt_password=fgt_vm_id, max_loop=1)
                if not b_succ_login or not self.cookie.get("csrftoken"):
                    continue
                session_key = self.cookie["csrftoken"]
                url = f"https://{self.fgt_private_ip}{self.fgt_login_port}/loginpwd_change"
                header = {
                    "Content-Type": "application/json",
                    "Cookie": self.cookie["cookie"],
                    "X-CSRFTOKEN": self.cookie["csrftoken"]
                }
                params = {
                    "CSRF_TOKEN" : self.cookie["csrftoken"],
                    "old_pwd" : fgt_vm_id,
                    "pwd1" : self.fgt_password,
                    "pwd2" : self.fgt_password,
                    "confirm": 1
                }
                body = None
            try:
                response = requests.post(url, headers=header, params=params, json=body, verify=False, timeout=20)
                if response.status_code == 200:
                    if api == "authentication":
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
                        response_text = response.text
                        if "document.location" in response_text:
                            b_succ = True
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
            self.logger.info(f"Sleep {i} 10 sec.")
            time.sleep(10)
        if b_succ:
            # Logout
            url = f"https://{self.fgt_private_ip}{self.fgt_login_port}/api/v2/authentication"
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

    def check_get_http(self):
        self.logger.info("Check get system status.")
        url = f"https://{self.fgt_private_ip}{self.fgt_login_port}/api/v2/monitor/system/status"
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

class Dynamodb:
    def __init__(self):
        self.logger = logging.getLogger("lambda")
        self.logger.setLevel(logging.INFO)
        self.dynamodb_table_name = os.getenv("dynamodb_table_name")
        self.dydb_endpoint_url = os.getenv("dydb_endpoint_url")
        self.dynamodb_client = boto3.client(
            service_name = "dynamodb",
            endpoint_url = "https://" + self.dydb_endpoint_url
        )
        self.return_json = {
            'ErrorMsg': None,
            'ResponseContent': None
        }

    def main(self, event):
        self.logger.info(f"Start internal lambda function for DynamoDB service.")
        operation = event["operation"]
        parameters = event["parameters"]
        if operation == "get_item":
            missed_var_list = Helper.check_missed_var(["category", "attributes"], parameters)
            if missed_var_list:
                self.return_json['ErrorMsg'] = "Could not find parameter: " + ", ".join(missed_var_list) + "."
                return
            rst = self.get_item_from_dydb(parameters["category"], parameters["attributes"])
            self.return_json['ResponseContent'] = rst
        elif operation == "put_item":
            missed_var_list = Helper.check_missed_var(["category", "attribute_name", "attribute_content"], parameters)
            if missed_var_list:
                self.return_json['ErrorMsg'] = "Could not find parameter: " + ", ".join(missed_var_list) + "."
                return
            b_succ = self.put_item_to_dydb(parameters["category"], parameters["attribute_name"], parameters["attribute_content"])
            if not b_succ:
                self.return_json['ErrorMsg'] = "Could not put item to DynamoDB."
        elif operation == "add_item":
            missed_var_list = Helper.check_missed_var(["category", "attribute_name", "attribute_content"], parameters)
            if missed_var_list:
                self.return_json['ErrorMsg'] = "Could not find parameter: " + ", ".join(missed_var_list) + "."
                return
            b_succ = self.add_item_to_dydb(parameters["category"], parameters["attribute_name"], parameters["attribute_content"])
            if not b_succ:
                self.return_json['ErrorMsg'] = "Could not add item to DynamoDB."
        elif operation == "remove_item":
            missed_var_list = Helper.check_missed_var(["category", "attribute_name", "attribute_content"], parameters)
            if missed_var_list:
                self.return_json['ErrorMsg'] = "Could not find parameter: " + ", ".join(missed_var_list) + "."
                return
            b_succ = self.remove_item_from_dydb(parameters["category"], parameters["attribute_name"], parameters["attribute_content"])
            if not b_succ:
                self.return_json['ErrorMsg'] = "Could not remove item from DynamoDB."
        else:
            self.return_json['ErrorMsg'] = f"Unknown operation {operation}."

    def get_item_from_dydb(self, category, attributes):
        rst = {}
        try:
            response = self.dynamodb_client.get_item(
                TableName=self.dynamodb_table_name,
                Key={
                    'Category': {
                        'S': category,
                    }
                },
                AttributesToGet=attributes
            )
            resp_content = response.get("Item")
            for attr_name in attributes:
                if attr_name in resp_content:
                    rst[attr_name] = self.convert_aws_dydb_to_normal_format(resp_content[attr_name])
        except Exception as err:
            self.logger.error(f"Could not get item from Dynamo DB table: {err}")
        return rst

    def put_item_to_dydb(self, category, attribute_name, attribute_content):
        aws_format_content = self.convert_to_aws_dydb_format(attribute_content)
        if not aws_format_content:
            self.logger.info(f"Attribute content is empty: {attribute_content}")
            return self.remove_item_from_dydb(category, attribute_name, attribute_content)
        b_succ= False
        try:
            response = self.dynamodb_client.update_item(
                TableName=self.dynamodb_table_name,
                Key={
                    'Category': {
                        'S': category,
                    }
                },
                AttributeUpdates={
                    attribute_name: {
                        'Value': aws_format_content
                    }
                })
            b_succ = True
        except Exception as err:
            self.logger.error(f"Could not update item in Dynamo DB table: {err}")
        return b_succ

    def add_item_to_dydb(self, category, attribute_name, attribute_content):
        if type(attribute_content) is list:
            attribute_content = set(attribute_content)
        if type(attribute_content) not in [set, int, float]:
            self.logger.error(f"Could not do the ADD operation for attribute type: {type(attribute_content)}")
            return False
        aws_format_content = self.convert_to_aws_dydb_format(attribute_content)
        if not aws_format_content:
            self.logger.info(f"Attribute content is empty: {attribute_content}")
            return False
        b_succ= False
        try:
            response = self.dynamodb_client.update_item(
                TableName=self.dynamodb_table_name,
                Key={
                    'Category': {
                        'S': category,
                    }
                },
                AttributeUpdates={
                    attribute_name: {
                        'Value': aws_format_content,
                        'Action': 'ADD'
                    }
                })
            b_succ = True
        except Exception as err:
            self.logger.error(f"Could not add item in Dynamo DB table: {err}")
        return b_succ

    def remove_item_from_dydb(self, category, attribute_name, attribute_content):
        if type(attribute_content) is list:
            attribute_content = set(attribute_content)
        aws_format_content = self.convert_to_aws_dydb_format(attribute_content)
        if not aws_format_content:
            self.logger.info(f"Attribute content is empty: {attribute_content}")
            return False
        b_succ = False
        attribute_value = {
            'Action': 'DELETE'
        }
        if aws_format_content:
            attribute_value["Value"] = aws_format_content
        try:
            response = self.dynamodb_client.update_item(
                TableName=self.dynamodb_table_name,
                Key={
                    'Category': {
                        'S': category,
                    }
                },
                AttributeUpdates={
                    attribute_name: attribute_value
                }
            )
            b_succ = True
        except Exception as err:
            self.logger.error(f"Could not remove item in Dynamo DB table: {err}")
        return b_succ

    def convert_to_aws_dydb_format(self, input_value):
        rst = {}
        if input_value == None:
            return rst
        aws_datatype = ""
        content = input_value
        input_type = type(input_value)
        if input_type is str:
            aws_datatype = "S"
        elif input_type is int or input_type is float:
            aws_datatype = "N"
            content = str(input_value)
        elif input_type is bool:
            aws_datatype = "BOOL"
        elif input_type is set:
            if not input_value:
                return rst
            for ele in input_value:
                ele_type = type(ele)
                break
            if ele_type is str:
                aws_datatype = "SS"
                content = list(input_value)
            elif ele_type is int or ele_type is float:
                aws_datatype = "NS"
                content = [str(e) for e in input_value]
        elif input_type is list:
            if not input_value:
                return {
                    "L": []
                }
            aws_datatype = "L"
            content = [self.convert_to_aws_dydb_format(e) for e in input_value]
        elif input_type is dict:
            if not input_value:
                return {
                    "M": {}
                }
            aws_datatype = "M"
            content = {}
            for k, v in input_value.items():
                content[k] = self.convert_to_aws_dydb_format(v)

        rst = {
            aws_datatype: content
        }
        return rst

    def convert_aws_dydb_to_normal_format(self, input_dict):
        if not input_dict:
            return input_dict
        rst = None
        for v_type, v_content in input_dict.items():
            if v_type == "M":
                rst = {}
                for k, v in v_content.items():
                    rst[k] = self.convert_aws_dydb_to_normal_format(v)
            elif v_type == "L":
                rst = [self.convert_aws_dydb_to_normal_format(e) for e in v_content]
            elif v_type == "NULL" and v_content:
                rst = None
            else:
                rst = v_content
            break
        return rst

 
def lambda_handler(event, context):
    service = event["service"]
    response = None
    ## FortiGate configuration operations
    if service == "fgt_vm":
        fgtObject = FgtConf()
        fgtObject.main(event)
        response = fgtObject.return_json
    elif service == "dynamodb":
        dydbObject = Dynamodb()
        dydbObject.main(event)
        response = dydbObject.return_json
    else:
        response = {
            'ErrorMsg': f"Unknown service: {service}.",
            'ResponseContent': None
        }
    return response