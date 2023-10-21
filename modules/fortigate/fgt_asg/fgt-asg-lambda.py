import os
import json
import logging
import time
import base64
import urllib
import requests
import re
import uuid

import boto3
import botocore
from botocore.exceptions import ClientError

class NetworkInterface:
    def __init__(self):
        self.logger = logging.getLogger("network_interface")
        self.logger.setLevel(logging.INFO)
        self.ec2_client = boto3.client("ec2")
        self.s3_client = boto3.client("s3")
        self.s3_bucket_name = os.getenv("lic_s3_name")
        self.dynamodb_client = boto3.client("dynamodb")
        self.dynamodb_table_name = os.getenv("dynamodb_table_name")
        self.intf_track_file_name = "intf_track.json"

    def main(self, event):
        self.logger.info(f"Do interface config")
        self.fgt_vm_id = event["detail"]["EC2InstanceId"]
        detail_type = event["detail-type"]
        self.instance_detail = self.ec2_client.describe_instances(InstanceIds=[self.fgt_vm_id])
        self.fgt_vm_intfs = {}
        for intf in self.instance_detail['Reservations'][0]['Instances'][0]['NetworkInterfaces']:
            cur_device_index = str(intf.get("Attachment").get("DeviceIndex"))
            self.fgt_vm_intfs[cur_device_index] = intf

        if detail_type == "EC2 Instance-launch Lifecycle Action":
            self.do_launch()
        elif detail_type == "EC2 Instance-terminate Lifecycle Action":
            self.do_terminate()
        if detail_type == "EC2 Instance Launch Successful":
            self.save_intf()
            return
        else:
            self.logger.info(f"Can not identify detail-type: {detail_type}")
            return
        
        self.complete_lifecycle(event)

    def do_launch(self):
        self.logger.info(f"Do launch fgt vm instance: {self.fgt_vm_id}")
        intf_setting = json.loads(os.getenv('network_interfaces'))
        fgt_az = self.instance_detail['Reservations'][0]['Instances'][0]['Placement']['AvailabilityZone']
        for intf_name, intf_conf in intf_setting.items():
            # Ignore if the interface already exist
            if str(intf_conf["device_index"]) in self.fgt_vm_intfs:
                continue
            # Create interface
            cur_intf_id = self.create_interface(intf_name, intf_conf, fgt_az)
            if cur_intf_id == None:
                continue
            # Attach the interface to FortiGate VM instance
            attach_id = self.attach_intf(cur_intf_id, intf_conf["device_index"])
            if attach_id == None:
                self.delete_interface(cur_intf_id)
                continue
            self.set_delete_on_termination(cur_intf_id, attach_id)
            # Create and associate Public IP if needed
            if "enable_public_ip" in intf_conf and intf_conf["enable_public_ip"] :
                self.associate_pub_ip(cur_intf_id, intf_conf)

    def do_terminate(self):
        self.logger.info(f"Do terminate fgt vm instance: {self.fgt_vm_id}")
        intf_track_dict = self.get_intf()
        cur_fgt_intf_dict = intf_track_dict.get(self.fgt_vm_id, {})
        # Merge intfs info
        for d_index, intf in cur_fgt_intf_dict.items():
            if d_index not in self.fgt_vm_intfs:
                self.logger.info(f"Add interface index: {d_index}")
                self.fgt_vm_intfs[d_index] = intf
        for d_index, intf in self.fgt_vm_intfs.items():
            if str(d_index) == "0":
                continue
            self.clean_up_intf(intf)
        self.remove_intf()

    def clean_up_intf(self, intf):
        self.logger.info(f"Clean up interface: {intf}")
        ## Release EIP if exist
        try:
            if "Association" in intf:
                pub_ip = intf["Association"].get("PublicIp")
                self.logger.info(f"Release EIP: {pub_ip}")
                addr = self.ec2_client.describe_addresses(PublicIps=[pub_ip])
                association_id = addr.get('Addresses')[0].get('AssociationId')
                allocation_id = addr.get('Addresses')[0].get('AllocationId')
                if association_id:
                    self.ec2_client.disassociate_address(AssociationId=association_id)
                if allocation_id:
                    self.ec2_client.release_address(AllocationId=allocation_id)
        except Exception as e:
            self.logger.info(f"Failed in release EIP: {e}")
        ## Delete interface if DeleteOnTermination is False
        try:
            if not (intf.get("Attachment").get("DeleteOnTermination")):
                attach_id = intf.get("Attachment").get("AttachmentId")
                intf_id = intf.get("NetworkInterfaceId")
                response = self.ec2_client.detach_network_interface(AttachmentId = attach_id)
                max_try = 10
                detached = False
                for i in range(max_try):
                    self.logger.info(f"Check interface status try: {i} times.")
                    cur_intf_des = self.ec2_client.describe_network_interfaces(NetworkInterfaceIds=[intf_id]).get("NetworkInterfaces")[0]
                    if "Attachment" not in cur_intf_des or cur_intf_des.get("Attachment").get("Status") == "detached":
                        detached = True
                        break
                    time.sleep(1)
                if detached:
                    self.delete_interface(intf_id)
                else:
                    self.logger.error(f"Could not detach network interface: {intf_id}")
        except Exception as e:
            self.logger.info(f"Failed in delete interface: {e}")
            
    def save_intf(self):
        self.lock_intf_track_file()
        try:
            intf_track_dict = self.get_intf_track_dict()
            if intf_track_dict != None:
                intf_track_dict[self.fgt_vm_id] = self.fgt_vm_intfs
                self.update_intf_track_file(intf_track_dict)
        except Exception as e:
            self.logger.error(f"Exception when save interface track file: {e}")
        self.unlock_intf_track_file()

    def remove_intf(self):
        self.lock_intf_track_file()
        try:
            intf_track_dict = self.get_intf_track_dict()
            if intf_track_dict != None:
                intf_track_dict.pop(self.fgt_vm_id, None)
                self.update_intf_track_file(intf_track_dict)
        except Exception as e:
            self.logger.error(f"Exception when remove instance record from interface track file: {e}")
        self.unlock_intf_track_file()

    def get_intf(self):
        self.lock_intf_track_file()
        try:
            intf_track_dict = self.get_intf_track_dict()
            if intf_track_dict == None:
                intf_track_dict = {}
        except Exception as e:
            self.logger.error(f"Exception when get interface track file: {e}")
        self.unlock_intf_track_file()
        return intf_track_dict

    def create_interface(self, intf_name, intf_conf, fgt_az):
        self.logger.info(f"Create interface: {intf_name}")
        try:
            private_ips = []
            if "private_ips" in intf_conf:
                primary_set = True
                for cur_ip in intf_conf["private_ips"]:
                    cur_dic = {
                        'Primary': primary_set,
                        'PrivateIpAddress': cur_ip
                    }
                    private_ips.append(cur_dic)
                    primary_set = False
            subnet_id = intf_conf["subnet_id_map"].get(fgt_az)
            if not subnet_id:
                self.logger.error(f"Could not get the Subnet ID of AZ: {fgt_az}")
                return None
            intf = self.ec2_client.create_network_interface(
                Description        = intf_conf["description"] if "description" in intf_conf else "",
                SubnetId           = subnet_id, 
                Groups             = intf_conf["security_groups"] if "security_groups" in intf_conf else [],
                PrivateIpAddresses = private_ips
            )
            intf_id = intf['NetworkInterface']['NetworkInterfaceId']
            return intf_id
        except ClientError as e:
            self.logger.error(f"Error creating network interface: {e.response['Error']['Code']}")
            return None

    def attach_intf(self, cur_intf_id, device_index):
        self.logger.info(f"Attach interface: {cur_intf_id}, device index: {device_index}")
        try:
            attach_intf = self.ec2_client.attach_network_interface(
                DeviceIndex        = device_index,
                InstanceId         = self.fgt_vm_id,
                NetworkInterfaceId = cur_intf_id
            )
            attach_intf_id = attach_intf['AttachmentId']
            return attach_intf_id
        except ClientError as e:
            self.logger.error(f"Error attaching network interface {cur_intf_id}: {e.response['Error']['Code']}")
            return None

    def set_delete_on_termination(self, cur_intf_id, attach_id):
        self.logger.info(f"Set DeleteOnTermination for interface: {cur_intf_id}.")
        try:
            self.ec2_client.modify_network_interface_attribute(
                NetworkInterfaceId        = cur_intf_id,
                Attachment={
                    'AttachmentId': attach_id,
                    'DeleteOnTermination': True
                }
            )
        except ClientError as e:
            self.logger.error(f"Error attaching network interface {cur_intf_id}: {e.response['Error']['Code']}")

    def associate_pub_ip(self, cur_intf_id, intf_conf):
        self.logger.info(f"Associate public ip: {cur_intf_id}.")
        eip_id = ""
        if "existing_eip_id" in intf_conf:
            eip_id = intf_conf["existing_eip_id"]
        else:
            try:
                if "public_ipv4_pool" in intf_conf:
                    public_ip_allocation = self.ec2_client.allocate_address(
                        Domain         = 'vpc',
                        PublicIpv4Pool = intf_conf["public_ipv4_pool"],
                    )
                else:
                    public_ip_allocation = self.ec2_client.allocate_address(
                        Domain         = 'vpc',
                    )
                eip_id = public_ip_allocation['AllocationId']
            except ClientError as e:
                self.logger.error(f"Error creating Elastic IP address : {e.response['Error']['Code']}")
                return None
        try:
            associate_pub_ip = self.ec2_client.associate_address(
                AllocationId       = eip_id,
                NetworkInterfaceId = cur_intf_id
            )
            associate_pub_ip_id = associate_pub_ip['AssociationId']
            return associate_pub_ip_id
        except ClientError as e:
            self.logger.error(f"Error associate network interface {cur_intf_id} and Elastic IP {eip_id} : {e.response['Error']['Code']}")
            self.ec2_client.release_address(AllocationId = eip_id)
            return None

    def delete_interface(self, cur_intf_id):
        self.logger.info(f"Delete interface: {cur_intf_id}.")
        response = ""
        try:
            response = self.ec2_client.delete_network_interface(NetworkInterfaceId=cur_intf_id)
        except ClientError as e:
            self.logger.error(f"Error deleting network interface {cur_intf_id}: {e.response['Error']['Code']}, response: {response}")

    def complete_lifecycle(self, event):
        self.logger.info(f"Complete lifecycle action.")
        asg_client = boto3.client('autoscaling')
        event_detail = event["detail"]
        try:
            asg_client.complete_lifecycle_action(
                LifecycleHookName=event_detail.get('LifecycleHookName', ""),
                AutoScalingGroupName=event_detail.get('AutoScalingGroupName', ""),
                LifecycleActionToken=event_detail.get('LifecycleActionToken', ""),
                LifecycleActionResult='CONTINUE'
            )
        except ClientError as e:
            self.logger.error(f"Error completing life cycle hook for instance: {e.response['Error']['Code']}")

    def lock_intf_track_file(self):
        self.logger.info("Lock interface track file from S3 bucket.")
        self.lock_id = str(uuid.uuid1())
        b_succ = False
        # Get tagging
        max_loop = 60
        go_next = False
        for i in range(max_loop):
            try:
                b_exist = self.check_object_exist()
                if not b_exist:
                    self.create_intf_track_file()
                    break
                response = self.s3_client.get_object_tagging(Bucket=self.s3_bucket_name, Key=self.intf_track_file_name)
                intf_track_tags = response.get("TagSet")

                locked_by_other = False
                for tag in intf_track_tags:
                    if tag["Key"] == 'lock_id' and tag["Value"]:
                        locked_by_other = True
                        break
                if locked_by_other:
                    time.sleep(2)
                    continue
                go_next = True
                break
            except botocore.exceptions.ClientError as e:
                self.logger.info(f"Could not get tags of  file {self.intf_track_file_name}: {e}")
                self.create_intf_track_file()
                break
        
        # Update tagging
        if go_next:
            try:
                response = self.s3_client.put_object_tagging(
                    Bucket=self.s3_bucket_name, 
                    Key=self.intf_track_file_name,
                    Tagging={
                        'TagSet': [
                            {
                                'Key': 'lock_id',
                                'Value': self.lock_id
                            },
                        ]
                    })
            except botocore.exceptions.ClientError as e:
                self.logger.info(f"Could not get tags of  file {self.intf_track_file_name}: {e}")
        # Check lock success
        b_succ = self.check_lock_status("lock")
        if b_succ:
            self.logger.info(f"Lock interface track file sussess: {self.lock_id}")

        return b_succ

    def unlock_intf_track_file(self):
        self.logger.info("Unlock interface track file from S3 bucket.")
        b_succ = False
        # Get tagging
        go_next = True
        try:
            response = self.s3_client.get_object_tagging(Bucket=self.s3_bucket_name, Key=self.intf_track_file_name)
            intf_track_tags = response.get("TagSet")
            if not intf_track_tags:
                self.logger.error(f"Can not find lock info in tags.")
            else:
                locked_by_other = False
                for tag in intf_track_tags:
                    if tag["Key"] == 'lock_id':
                        if not tag["Value"] or tag["Value"] != self.lock_id:
                            vl = tag["Value"]
                            self.logger.info(f"Interface track file is not locked or locked by others: {vl}")
                            go_next = False
                            break
        except botocore.exceptions.ClientError as e:
            self.logger.info(f"Could not get tags of file {self.intf_track_file_name}: {e}")
            go_next = False
        
        # Update tagging
        if go_next:
            try:
                response = self.s3_client.put_object_tagging(
                    Bucket=self.s3_bucket_name, 
                    Key=self.intf_track_file_name,
                    Tagging={
                        'TagSet': [
                            {
                                'Key': 'lock_id',
                                'Value': ""
                            },
                        ]
                    })
                b_succ = True
            except botocore.exceptions.ClientError as e:
                self.logger.info(f"Could not get tags of file {self.intf_track_file_name}: {e}")
        # Check unlock success
        b_succ = self.check_lock_status("unlock")
        if b_succ:
            self.logger.info(f"Unlock interface track file sussess: {self.lock_id}")
        return b_succ

    def check_lock_status(self, status):
        status_value = ""
        if status == "lock":
            status_value = self.lock_id
        b_succ = False
        try:
            response = self.s3_client.get_object_tagging(Bucket=self.s3_bucket_name, Key=self.intf_track_file_name)
            intf_track_tags = response.get("TagSet")
            if not intf_track_tags:
                self.logger.error(f"Did not lock the file.")
            else:
                for tag in intf_track_tags:
                    if tag["Key"] == 'lock_id':
                        if tag["Value"] == status_value:
                            b_succ = True
                            break
        except botocore.exceptions.ClientError as e:
            self.logger.info(f"Could not get tags of file {self.intf_track_file_name}: {e}")
        return b_succ

    def create_intf_track_file(self):
        self.logger.info("Create interface track file on S3 bucket.")
        intf_track_dict = {}

        return self.update_intf_track_file(intf_track_dict)

    def update_intf_track_file(self, intf_track_dict):
        self.logger.info("Update interface track file.")
        file_body = json.dumps(intf_track_dict, default=str)
        b_succ = False
        try:
            response = self.s3_client.put_object(
                Bucket=self.s3_bucket_name, 
                Key=self.intf_track_file_name, 
                Body=file_body,
                Tagging=f"lock_id={self.lock_id}"
                )
            b_succ = True
        except Exception as err:
            self.logger.error(f"Could not save S3 object: {err}")
        return b_succ

    def get_intf_track_dict(self):
        self.logger.info("Get interface track file from S3 bucket.")
        intf_track_dict = {}
        try:
            response = self.s3_client.get_object(Bucket=self.s3_bucket_name, Key=self.intf_track_file_name)
            intf_track_dict = json.loads(response.get("Body").read())
            if intf_track_dict == None or intf_track_dict == "":
                self.logger.info(f"File {self.intf_track_file_name} not been created.")
                return None
        except botocore.exceptions.ClientError as e:
            self.logger.info(f"Could not get file {self.intf_track_file_name}: {e}")
        return intf_track_dict

    def check_object_exist(self):
        b_exist = True
        try:
            response = self.s3_client.get_object(Bucket=self.s3_bucket_name, Key=self.intf_track_file_name)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                b_exist = False
        return b_exist

 # AWS Dynamo DB operations
    def get_item_from_dydb(self, category, attributes):
        rst = None
        try:
            response = self.dynamodb_client.get_item(
                TableName=self.dynamodb_table_name,
                Key={
                    'Category': {
                        'S': category,
                    }
                },
                AttributesToGet=attributes)
            rst = response.get("Item")
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
        aws_format_content = self.convert_to_aws_dydb_format(attribute_content)
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

class FgtConf:
    def __init__(self, event):
        self.logger = logging.getLogger("fgt_config")
        self.logger.setLevel(logging.INFO)
        self.ec2_client = boto3.client("ec2")
        self.s3_client = boto3.client("s3")
        self.dynamodb_client = boto3.client("dynamodb")
        self.lambda_client = boto3.client("lambda")

        self.logger.info(f"Do FGT config.")
        self.logger.info(f"Event detail:: {event}")
        self.fgt_vm_id = event["detail"]["EC2InstanceId"]
        self.detail_type = event["detail-type"]
        self.cookie = {}
        self.lic_track_file_name = "asg-fgt-lic-track.json"
        self.dynamodb_table_name = os.getenv("dynamodb_table_name")
        self.enable_fgt_system_autoscale = os.getenv("enable_fgt_system_autoscale") == "true"
        self.fgt_system_autoscale_psksecret = os.getenv("fgt_system_autoscale_psksecret")
        self.fgt_login_port_number = os.getenv("fgt_login_port_number")
        self.internal_lambda_name = os.getenv("internal_lambda_name")
        self.asg_name = os.getenv("asg_name")

    def main(self):
        if self.detail_type == "EC2 Instance Launch Successful":
            self.do_launch()
        elif self.detail_type == "EC2 Instance-terminate Lifecycle Action":
            self.do_terminate()
        else:
            self.logger.debug(f"Can not identify detail-type: {self.detail_type}")
            return
    
    def do_launch(self):
        self.logger.info("Do launch envent.")
        instance_detail = self.ec2_client.describe_instances(InstanceIds=[self.fgt_vm_id])
        # Add name for the instance
        self.update_tags(
            [self.fgt_vm_id], 
            [{
                'Key': 'Name',
                'Value': self.asg_name
            }]
        )
        # Get private IP
        fgt_private_ip = self.get_private_ip(instance_detail['Reservations'][0]['Instances'][0])
        if not fgt_private_ip:
            self.logger.error("Can not find private IP.")
            return
        # Change password
        b_succ = self.change_password(fgt_private_ip, self.fgt_vm_id)
        if not b_succ:
            self.logger.error(f"Could not change password.")
            return
        
        # Update in Dynamo DB
        self.add_asg_instance_dydb(self.fgt_vm_id)

        # Upload license
        need_license = os.getenv("need_license") == "true"
        if need_license:
            self.s3_bucket_name = os.getenv("lic_s3_name")
            # Update Serial numbers
            b_succ = self.update_all_sn_list()
            b_succ = self.upload_license(fgt_private_ip, self.fgt_vm_id)
            if not b_succ:
                return

        # Configure the FortiGate instance
        time.sleep(10)
        self.intf_setting = json.loads(os.getenv('network_interfaces'))
        self.fgt_az = instance_detail['Reservations'][0]['Instances'][0]['Placement']['AvailabilityZone']
        self.fgt_primary_ip, self.fgt_primary_port = self.get_primary_ip(instance_detail['Reservations'][0]['Instances'][0])

        config_content = self.gen_config_content(self.fgt_vm_id)
        b_succ = self.upload_config(config_content, fgt_private_ip)

        
    def do_terminate(self):
        need_license = os.getenv("need_license")
        if not need_license:
            return
        self.s3_bucket_name = os.getenv("lic_s3_name")
        self.logger.info("Do terminate envent.")
        # Update Serial numbers
        b_succ = self.update_all_sn_list()
        # Update license record 
        b_updated = self.release_lic(self.fgt_vm_id)
        if not b_updated:
            used_sn_map = self.get_used_sn_map()
            if self.fgt_vm_id in used_sn_map:
                sn = used_sn_map.pop(self.fgt_vm_id)
                self.update_used_sn_map(used_sn_map)
                self.add_available_sn({sn})
                # Deactive current token
                oauth_token = self.get_fortiflex_oauth_token()
                if oauth_token:
                    self.generate_vm_token(sn, oauth_token)
        # Update instance info on Dynamo DB
        self.remove_asg_instance_dydb(self.fgt_vm_id)
        if self.enable_fgt_system_autoscale:
            instance_detail = self.ec2_client.describe_instances(InstanceIds=[self.fgt_vm_id])
            self.update_tags(
                [self.fgt_vm_id], 
                [{
                    'Key': 'Autoscale Role',
                    'Value': ''
                }]
            )
            self.image_id = instance_detail['Reservations'][0]['Instances'][0]['ImageId']
            self.fgt_primary_ip, self.fgt_primary_port = self.get_primary_ip(instance_detail['Reservations'][0]['Instances'][0])
            self.check_primary(self.fgt_vm_id)

# Instance information
    def get_private_ip(self, instance):
        rst = None
        if instance.get("PublicIpAddress"):
            rst = instance.get('PrivateIpAddress')
        if not rst:
            for intf in instance['NetworkInterfaces']:
                if "PrivateIpAddress" not in intf:
                    continue
                if "Association" not in intf or not intf["Association"].get("PublicIp"):
                    continue
                cur_private_ip = intf.get("PrivateIpAddress")
                if cur_private_ip:
                    rst = cur_private_ip
                    break
        return rst

    def get_primary_ip(self, instance):
        self.logger.info(f"Get primary ip for current instance.")
        p_ip = ""
        p_port = ""
        interfaces = instance.get("NetworkInterfaces")
        if not interfaces:
            self.logger.error(f"Could not get network instances.")
            return p_ip, p_port
        for interface in interfaces:
            if "Association" not in interface:
                continue
            p_ip = interface.get("PrivateIpAddress")
            d_index = interface.get("Attachment").get("DeviceIndex")
            p_port = f"port{d_index + 1}"
        if not p_ip:
            p_ip = instance.get('PrivateIpAddress')
            p_port = f"port1"
        return p_ip, p_port

# Invode lambda function
    def invoke_lambda(self, payload, invocation_type=""):
        b_succ= False
        if invocation_type == "":
            invocation_type = 'RequestResponse'
        try:
            response = self.lambda_client.invoke(
                FunctionName = self.internal_lambda_name,
                InvocationType = invocation_type,
                Payload = json.dumps(payload)
            )
            if "StatusCode" in response and response["StatusCode"] in [200, 202, 204]:
                b_succ = True
            else:
                errmsg = ""
                if "FunctionError" in response:
                    errmsg = response["FunctionError"]
                self.logger.error(f"Invoke lambda function failed. {errmsg}")
        except Exception as err:
            self.logger.error(f"Could not invoke lambda function, error: {err}")
        return b_succ
    
# License
    def upload_license(self, fgt_private_ip, fgt_vm_id):
        # Get license, license_type: "token", "file"; license_content：token if license_type is token, file name if license_type is file
        license_type, license_content, sn_or_file_name = self.get_license(fgt_vm_id)
        if license_type == "":
            self.logger.error(f"Could not get license!")
            return False

        # Upload license
        if license_type == "token":
            payload = {
                "private_ip" : fgt_private_ip,
                "operation" : "upload_license",
                "parameters" : {
                    "license_type": license_type,
                    "license_content": license_content
                }
            }
            b_succ = self.invoke_lambda(payload)
            if b_succ:
                used_sn_map = self.get_used_sn_map()
                used_sn_map[fgt_vm_id] = sn_or_file_name
                self.update_used_sn_map(used_sn_map)
            else:
                self.add_available_sn({sn_or_file_name})
                self.logger.error("Could not activate the token on FortiGate instance.")
        elif license_type == "file":
            lic_file_content = self.get_lic_file_content(license_content)
            payload = {
                "private_ip" : fgt_private_ip,
                "operation" : "upload_license",
                "parameters" : {
                    "license_type": license_type,
                    "license_content": lic_file_content
                }
            }
            b_succ = self.invoke_lambda(payload)
            # Update license track file if upload license successfully
            if b_succ:
                self.logger.info("Upload license file success.")
            else:
                self.logger.error(f"Could not active license!")
                self.release_lic(fgt_vm_id)
        return b_succ

    def get_license(self, fgt_vm_id):
        self.logger.info("Get next available license.")
        # Get license file first
        b_locked = self.lock_lic_track_file()
        if b_locked:
            b_find = False
            try:
                go_next = True
                license_type = ""
                license_content = ""
                if self.s3_bucket_name == "":
                    go_next = False
                if go_next:
                    # Check whether license track file exist or not
                    lic_track_dict = self.get_lic_track_dict()
                    if not lic_track_dict:
                        go_next = False
                if go_next:
                    if "file" in lic_track_dict:
                        if "available" in lic_track_dict["file"] and lic_track_dict["file"]["available"]:
                            license_type  = "file"
                            license_content = lic_track_dict["file"]["available"][0]
                            b_find = True      
                    if b_find:
                        lic_track_dict[license_type]["available"].remove(license_content)
                        lic_track_dict[license_type]["used"][fgt_vm_id] = license_content
                        self.update_lic_track_file(lic_track_dict)
            except Exception as e:
                self.logger.error(f"Exception when get license from license track file: {e}")
            self.unlock_lic_track_file()
            if b_find:
                return license_type, license_content, lic_track_dict
            self.logger.info("Could not get license file, try FortiFlex token.")
        # Get FortiFlex token
        # Check FortiFlex OAuth token
        oauth_token = self.get_fortiflex_oauth_token()
        if not oauth_token:
            self.logger.info(f"Could not get valid OAuth token.")
            return "", "", ""
        # Get serial number and generate vm token
        dydb_items = self.get_item_from_dydb("fortiflex", ["available_sn_list"])
        if dydb_items:
            if "available_sn_list" in dydb_items:
                available_sn_list = self.convert_aws_dydb_to_normal_format(dydb_items["available_sn_list"])
                if available_sn_list:
                    for cur_sn in available_sn_list:
                        vm_token = self.generate_vm_token(cur_sn, oauth_token)
                        if vm_token:
                            self.remove_available_sn({cur_sn})
                            return "token", vm_token, cur_sn
                else:
                    self.logger.info("Could not get available serial number.")
        
        return "", "", ""

    def update_lic_track_file(self, lic_track_dict):
        self.logger.info("Update license track file.")
        file_body = json.dumps(lic_track_dict)
        b_succ = False
        try:
            response = self.s3_client.put_object(
                Bucket=self.s3_bucket_name, 
                Key=self.lic_track_file_name, 
                Body=file_body,
                Tagging=f"lock_id={self.lock_id}"
                )
            b_succ = True
        except Exception as err:
            self.logger.error(f"Could not save S3 object: {err}")
        return b_succ
        
    def get_lic_track_dict(self):
        self.logger.info("Get license track file from S3 bucket.")
        lic_track_dict = {}
        try:
            response = self.s3_client.get_object(Bucket=self.s3_bucket_name, Key=self.lic_track_file_name)
            lic_track_dict = json.loads(response.get("Body").read())
            if not lic_track_dict:
                self.logger.info(f"File {self.lic_track_file_name} not been created.")
                return
            else:
                lic_track_dict = self.refresh_lic_track_dic(lic_track_dict)
        except botocore.exceptions.ClientError as e:
            self.logger.info(f"Could not get file {self.lic_track_file_name}: {e}")
        return lic_track_dict

    def create_lic_track_file(self):
        self.logger.info("Create license track file on S3 bucket.")
        lic_track_dict = {
            "token": {
                "available": [],
                "used": {}
            },
            "file": {
                "available": [],
                "used": {}
            }
        }

        return self.update_lic_track_file(lic_track_dict)

    def refresh_lic_track_dic(self, lic_track_dict):
        self.logger.info(f"Refresh lic track file.")
        try:
            response = self.s3_client.list_objects(Bucket=self.s3_bucket_name)
        except botocore.exceptions.NoSuchBucket as e:
            self.logger.error(f"Could not get S3 bucket: {e}")
            return {}

        new_lic_track_dict = {
            "token": {
                "available": [],
                "used": {}
            },
            "file": {
                "available": [],
                "used": {}
            }
        }
        file_list = response["Contents"]
        has_change = False
        unknow_file_list = []
        for item in file_list:
            file_name = item["Key"]
            if file_name == self.lic_track_file_name:
                continue
            if file_name.endswith(".lic"):
                bfind = False
                file_available = lic_track_dict["file"]["available"]
                file_used = lic_track_dict["file"]["used"]
                if file_used:
                    for k, v in file_used.items():
                        if v == file_name:
                            new_lic_track_dict["file"]["used"][k] = v
                            file_used.pop(k)
                            bfind = True
                            break
                if not bfind:
                    new_lic_track_dict["file"]["available"].append(file_name)
                    if file_available and file_name in file_available:
                        file_available.remove(file_name)
                    else:
                        has_change = True

            elif file_name.endswith(".json"):
                response = self.s3_client.get_object(Bucket=self.s3_bucket_name, Key=file_name)
                file_content = json.loads(response.get("Body").read())
                if type(file_content) is list:
                    for token in file_content:
                        bfind = False
                        token_available = lic_track_dict["token"]["available"]
                        token_used = lic_track_dict["token"]["used"]
                        if token_used:
                            for k, v in token_used.items():
                                if v == token:
                                    new_lic_track_dict["token"]["used"][k] = v
                                    token_used.pop(k)
                                    bfind = True
                                    break
                        if not bfind:
                            new_lic_track_dict["token"]["available"].append(token)
                            if token_available and token in token_available:
                                token_available.remove(token)
                            else:
                                has_change = True
            else:
                unknow_file_list.append(file_name)

        if has_change or lic_track_dict["token"]["available"] or lic_track_dict["token"]["used"] or lic_track_dict["file"]["available"] or lic_track_dict["file"]["used"]:
            has_change = True
        if has_change:
            self.update_lic_track_file(new_lic_track_dict)
        return new_lic_track_dict

    def get_lic_file_content(self, license_content):
        lic_file_content = ""
        try:
            response = self.s3_client.get_object(
                Bucket=self.s3_bucket_name,
                Key=license_content
            )
            lic_file_content = response.get("Body").read().decode('utf-8') 
        except ClientError as e:
            self.logger.error(f"Could not get S3 object: {e}")
        return lic_file_content

    def release_lic(self, fgt_vm_id):
        b_locked = self.lock_lic_track_file()
        if not b_locked:
            return False
        b_updated = False
        try:
            # Get license track file
            lic_track_dict = self.get_lic_track_dict()
            if lic_track_dict:
                # Update license track file
                for content_dic in lic_track_dict.values():
                    if fgt_vm_id in content_dic["used"]:
                        b_updated = True
                        lic_content = content_dic["used"].pop(fgt_vm_id)
                        content_dic["available"].append(lic_content)
                        break
                # Upload license track file to S3 bucket
                if not b_updated:
                    self.logger.info(f"Did not find instance id in license track file: {fgt_vm_id}")
                else:
                    self.update_lic_track_file(lic_track_dict)
        except Exception as e:
            self.logger.error(f"Exception when release instance to available in interface track file: {e}")
        self.unlock_lic_track_file()
        return b_updated

    def lock_lic_track_file(self):
        self.logger.info("Lock license track file from S3 bucket.")
        self.lock_id = str(uuid.uuid1())
        b_succ = False
        # Get tagging
        max_loop = 60
        go_next = False
        for i in range(max_loop):
            try:
                b_exist = self.check_object_exist()
                if not b_exist:
                    self.create_lic_track_file()
                    break
                response = self.s3_client.get_object_tagging(Bucket=self.s3_bucket_name, Key=self.lic_track_file_name)
                lic_track_tags = response.get("TagSet")
                lock_tag = None
                for tag in lic_track_tags:
                    if tag["Key"] == 'lock_id':
                        lock_tag = tag
                if not lock_tag:
                    self.logger.info(f"Lic track file tags is empty: {lic_track_tags}")
                    self.create_lic_track_file()
                    break
                else:
                    locked_by_other = False
                    if lock_tag["Value"]:
                        locked_by_other = True
                        break
                    if locked_by_other:
                        time.sleep(2)
                        continue
                    go_next = True
                    break
            except botocore.exceptions.ClientError as e:
                self.logger.info(f"Could not get tags of  file {self.lic_track_file_name}: {e}")
                self.create_lic_track_file()
                break
        
        # Update tagging
        if go_next:
            try:
                response = self.s3_client.put_object_tagging(
                    Bucket=self.s3_bucket_name, 
                    Key=self.lic_track_file_name,
                    Tagging={
                        'TagSet': [
                            {
                                'Key': 'lock_id',
                                'Value': self.lock_id
                            },
                        ]
                    })
            except botocore.exceptions.ClientError as e:
                self.logger.info(f"Could not get tags of file {self.lic_track_file_name}: {e}")
        # Check lock success
        b_succ = self.check_lock_status("lock")
        if b_succ:
            self.logger.info(f"Lock license track file sussess: {self.lock_id}")

        return b_succ

    def unlock_lic_track_file(self):
        self.logger.info("Unlock license track file from S3 bucket.")
        b_succ = False
        # Get tagging
        go_next = True
        try:
            response = self.s3_client.get_object_tagging(Bucket=self.s3_bucket_name, Key=self.lic_track_file_name)
            lic_track_tags = response.get("TagSet")
            if not lic_track_tags:
                self.logger.error(f"Can not find lock info in tags.")
            else:
                locked_by_other = False
                for tag in lic_track_tags:
                    if tag["Key"] == 'lock_id':
                        if not tag["Value"] or tag["Value"] != self.lock_id:
                            vl = tag["Value"]
                            self.logger.info(f"Lic track file is not locked or locked by others: {vl}")
                            go_next = False
                            break
        except botocore.exceptions.ClientError as e:
            self.logger.info(f"Could not get tags of file {self.lic_track_file_name}: {e}")
            go_next = False
        
        # Update tagging
        if go_next:
            try:
                response = self.s3_client.put_object_tagging(
                    Bucket=self.s3_bucket_name, 
                    Key=self.lic_track_file_name,
                    Tagging={
                        'TagSet': [
                            {
                                'Key': 'lock_id',
                                'Value': ""
                            },
                        ]
                    })
                b_succ = True
            except botocore.exceptions.ClientError as e:
                self.logger.info(f"Could not get tags of file {self.lic_track_file_name}: {e}")
        # Check unlock success
        b_succ = self.check_lock_status("unlock")
        if b_succ:
            self.logger.info(f"Unlock license track file sussess: {self.lock_id}")
        return b_succ

    def check_lock_status(self, status):
        status_value = ""
        if status == "lock":
            status_value = self.lock_id
        b_succ = False
        try:
            response = self.s3_client.get_object_tagging(Bucket=self.s3_bucket_name, Key=self.lic_track_file_name)
            lic_track_tags = response.get("TagSet")
            if not lic_track_tags:
                self.logger.error(f"Did not lock the file.")
            else:
                for tag in lic_track_tags:
                    if tag["Key"] == 'lock_id':
                        if tag["Value"] == status_value:
                            b_succ = True
                            break
        except botocore.exceptions.ClientError as e:
            self.logger.info(f"Could not get tags of file {self.lic_track_file_name}: {e}")
        return b_succ

    def check_object_exist(self):
        b_exist = True
        try:
            # s3.Object(self.s3_bucket_name, self.lic_track_file_name).load()
            response = self.s3_client.get_object(Bucket=self.s3_bucket_name, Key=self.lic_track_file_name)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                b_exist = False
        return b_exist

 # FortiFlex
  # FortiFlex API
    def verify_oauth_token(self, oauth_token):
        self.logger.info("Verify FortiFlex OAuth token.")
        b_valid = False
        expires_in = 0
        url = "https://customerapiauth.fortinet.com/api/v1/oauth/verify_token/?client_id=flexvm"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {oauth_token}"
        }
        response = requests.get(url, headers=header, verify=False, timeout=10)
        if response.status_code == 200:
            response_json = response.json()
            if response_json:
                if "expires_in" in response_json:
                    expires_in = response_json['expires_in']
                    b_valid = True
            else:
                self.logger.info("Could not get http return status")
        response.close()
        return b_valid, expires_in

    def refresh_oauth_token(self, oauth_refresh_token):
        self.logger.info("Refresh FortiFlex OAuth token.")
        new_oauth_token = ""
        url = "https://customerapiauth.fortinet.com/api/v1/oauth/token/"
        header = {
            "Content-Type": "application/json"
        }
        body = {
            "client_id": "flexvm",
            "grant_type":"refresh_token",
            "refresh_token": oauth_refresh_token
        }
        response = requests.post(url, headers=header, json=body, verify=False, timeout=10)
        if response.status_code == 200:
            response_json = response.json()
            if response_json:
                if "access_token" not in response_json or "refresh_token" not in response_json:
                    self.logger.error("The FortiFlex refresh token is not valid or been revoked. Please check and provide a valid refresh token.")
                    return ""
                new_oauth_token = response_json["access_token"]
                new_refresh_token = response_json["refresh_token"]
                b_succ = self.update_fortiflex_oauth_token(new_oauth_token)
                b_succ = self.update_fortiflex_refresh_token(new_refresh_token)
            else:
                self.logger.info("Could not get http return status")
        response.close()
        return new_oauth_token

  # AWS operations
   # Token related
    def get_fortiflex_oauth_token(self):
        dydb_items = self.get_item_from_dydb("fortiflex", ["oauth_token"])
        oauth_token = ""
        if dydb_items:
            if "oauth_token" in dydb_items:
                oauth_token = self.convert_aws_dydb_to_normal_format(dydb_items["oauth_token"])
        if oauth_token:
            b_valid, expires_in = self.verify_oauth_token(oauth_token)
            if b_valid:
                if expires_in > 120:
                    return oauth_token
        # If oauth_token not exist or will/already expired
        oauth_refresh_token = self.get_fortiflex_refresh_token()
        new_oauth_token = ""
        if oauth_refresh_token:
            new_oauth_token = self.refresh_oauth_token(oauth_refresh_token)
        if not new_oauth_token:
            oauth_refresh_token = os.getenv("fortiflex_refresh_token")
            if not oauth_refresh_token: # Variable fortiflex_refresh_token not been provided
                return ""
            new_oauth_token = self.refresh_oauth_token(oauth_refresh_token)
        return new_oauth_token

    def update_fortiflex_oauth_token(self, oauth_token):
        b_succ = self.put_item_to_dydb("fortiflex", "oauth_token", oauth_token)
        return b_succ
    
    def get_fortiflex_refresh_token(self):
        dydb_items = self.get_item_from_dydb("fortiflex", ["oauth_refresh_token"])
        oauth_refresh_token = ""
        if dydb_items:
            if "oauth_refresh_token" in dydb_items:
                oauth_refresh_token = self.convert_aws_dydb_to_normal_format(dydb_items["oauth_refresh_token"])
        return oauth_refresh_token

    def update_fortiflex_refresh_token(self, oauth_refresh_token):
        b_succ = self.put_item_to_dydb("fortiflex", "oauth_refresh_token", oauth_refresh_token)
        return b_succ
   
    def generate_vm_token(self, sn, oauth_token):
        self.logger.info("Generate VM token.")
        vm_token = ""
        url = "https://support.fortinet.com/ES/api/fortiflex/v2/entitlements/vm/token"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {oauth_token}"
        }
        body = {
            "serialNumber": sn
        }
        response = requests.post(url, headers=header, json=body, verify=False, timeout=10)
        if response.status_code == 200:
            response_json = response.json()
            if response_json:
                if "entitlements" not in response_json and not response_json["entitlements"]:
                    if "error" in response_json and not response_json["error"]:
                        err_msg = response_json["error"]
                        self.logger.error(f"Could not regenerate token for serial number {sn}, error msg: {err_msg}")
                    return ""
                vm_token = response_json["entitlements"][0]["token"]
            else:
                self.logger.info("Could not get http return status")
        response.close()
        return vm_token

   # Serial number related
    def update_all_sn_list(self):
        self.logger.info("Update all serial number list")
        config_sn_list = json.loads(os.getenv("fortiflex_sn_list"))
        if not config_sn_list:
            config_sn_list = []
        configid_list = json.loads(os.getenv("fortiflex_configid_list"))
        if not configid_list:
            configid_list = []
        for configid in configid_list:
            cur_sn_list = self.get_sn_by_configid(configid)
            config_sn_list.extend(cur_sn_list)
        if not config_sn_list:
            return False
        all_sn_list = set(config_sn_list)
        self.all_sn_list = all_sn_list
        # Update all_sn_list in Dynamo DB
        dydb_all_sn_list = []
        dydb_items = self.get_item_from_dydb("fortiflex", ["all_sn_list"])
        if dydb_items:
            if "all_sn_list" in dydb_items:
                dydb_all_sn_list = self.convert_aws_dydb_to_normal_format(dydb_items["all_sn_list"])
        dydb_all_sn_list = set(dydb_all_sn_list)
        if all_sn_list != dydb_all_sn_list:
            # Update all_sn_list
            self.put_item_to_dydb("fortiflex", "all_sn_list", all_sn_list)
            # Update available_sn_list
            used_sn_map = self.get_used_sn_map()
            used_sn_set = set(used_sn_map.values())
            new_available_sn_list = all_sn_list - used_sn_set
            removed_sn_list = dydb_all_sn_list - all_sn_list
            if new_available_sn_list:
                self.add_available_sn(new_available_sn_list)
            if removed_sn_list:
                self.remove_available_sn(removed_sn_list)
                for instance_id, sn in used_sn_map.items():
                    if sn in removed_sn_list:
                        self.logger.info(f"Change license for instance {instance_id}")
                        instance_detail = self.ec2_client.describe_instances(InstanceIds=[instance_id])
                        cur_private_ip = self.get_private_ip(instance_detail['Reservations'][0]['Instances'][0]) 
                        if not cur_private_ip:
                            self.logger.info(f"Can not find private IP for instance: {instance_id}")
                            continue
                        self.upload_license(cur_private_ip, instance_id)
        return True

    def get_sn_by_configid(self, configid):
        self.logger.info("Get serial numbers by config id.")
        oauth_token = self.get_fortiflex_oauth_token()
        if not oauth_token:
            self.logger.info(f"Could not get valid OAuth token.")
            return []
        sn_list = []
        url = "https://support.fortinet.com/ES/api/fortiflex/v2/entitlements/list"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {oauth_token}"
        }
        body = {
            "configId": configid
        }
        response = requests.post(url, headers=header, json=body, verify=False, timeout=10)
        if response.status_code == 200:
            response_json = response.json()
            if response_json:
                if "entitlements" not in response_json and not response_json["entitlements"]:
                    if "error" in response_json and not response_json["error"]:
                        err_msg = response_json["error"]
                        self.logger.error(f"Could not get sefial numbers by config id {configid}, error msg: {err_msg}")
                    return []
                for ele in response_json["entitlements"]:
                    if ele["status"] in {"ACTIVE", "PENDING"}:
                        sn_list.append(ele["serialNumber"])
            else:
                self.logger.info("Could not get http return status")
        response.close()
        return sn_list

    def get_next_available_sn(self):
        self.logger.info("Get next available serial number.")
        dydb_items = self.get_item_from_dydb("fortiflex", ["available_sn_list"])
        if dydb_items:
            if "available_sn_list" in dydb_items:
                available_sn_list = self.convert_aws_dydb_to_normal_format(dydb_items["available_sn_list"])
                if available_sn_list:
                    rst = available_sn_list[0]
                    self.remove_available_sn({rst})
                    return rst
        return None

    def add_available_sn(self, sn_set):
        self.logger.info(f"Add available serial number {sn_set} into Dynamo DB.")
        b_succ = self.add_item_to_dydb("fortiflex", "available_sn_list", sn_set)
        return b_succ

    def remove_available_sn(self, sn_set):
        self.logger.info(f"Remove available serial number {sn_set} from Dynamo DB.")
        b_succ = self.remove_item_from_dydb("fortiflex", "available_sn_list", sn_set)
        return b_succ

    def get_used_sn_map(self):
        self.logger.info(f"Get used serial number map.")
        used_sn_map = {}
        dydb_items = self.get_item_from_dydb("fortiflex", ["used_sn_map"])
        if dydb_items:
            if "used_sn_map" in dydb_items:
                used_sn_map = self.convert_aws_dydb_to_normal_format(dydb_items["used_sn_map"])
        return used_sn_map

    def update_used_sn_map(self, sn_map):
        self.logger.info(f"Update used serial number {sn_map} on Dynamo DB.")
        b_succ = self.put_item_to_dydb("fortiflex", "used_sn_map", sn_map)
        return b_succ

   # Tag related
    def update_tags(self, resource_list, tag_list):
        b_succ= False
        if not resource_list or not tag_list:
            return b_succ
        try:
            response = self.ec2_client.create_tags(
                Resources=resource_list,
                Tags=tag_list
            )
            b_succ = True
        except Exception as err:
            self.logger.error(f"Could not update item tags for {resource_list}, error: {err}")
        return b_succ

  # AWS Dynamo DB operations
    def get_item_from_dydb(self, category, attributes):
        rst = None
        try:
            response = self.dynamodb_client.get_item(
                TableName=self.dynamodb_table_name,
                Key={
                    'Category': {
                        'S': category,
                    }
                },
                AttributesToGet=attributes)
            rst = response.get("Item")
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

# FortiGate instances infomation of ASG
    def get_asg_instance_list_dydb(self):
        self.logger.info("Get instance list of ASG.")
        rst = []
        try:
            response = self.dynamodb_client.get_item(
                TableName=self.dynamodb_table_name,
                Key={
                    'Category': {
                        'S': 'asg_instances',
                    }
                },
                AttributesToGet=[
                    'instance_list'
                ])
            items = response.get("Item")
            if items:
                rst = items.get('instance_list').get('L') if items.get('instance_list') else None
        except Exception as err:
            self.logger.error(f"Could not get instance list of ASG: {err}")
        return rst

    def add_asg_instance_dydb(self, instance_id):
        self.logger.info("Add instance ID to Dynamo DB table.")
        cur_list = self.get_asg_instance_list_dydb()
        for instance_dict in cur_list:
            if instance_id in instance_dict.values():
                self.logger.info(f"Instance already in the instance list of DynamoDB: {instance_id}")
                return True
        cur_list.append({
            'S': instance_id
        })
        b_succ= False
        try:
            response = self.dynamodb_client.update_item(
                TableName=self.dynamodb_table_name,
                Key={
                    'Category': {
                        'S': 'asg_instances',
                    }
                },
                AttributeUpdates={
                    'instance_list': {
                        'Value': {
                            'L': cur_list
                        }
                    }
                })
            b_succ = True
        except Exception as err:
            self.logger.error(f"Could not add instance ID to Dynamo DB table: {err}")
        return b_succ

    def remove_asg_instance_dydb(self, instance_id):
        self.logger.info("Remove instance ID from Dynamo DB table.")
        cur_list = self.get_asg_instance_list_dydb()
        for instance_dict in cur_list:
            if instance_id in instance_dict.values():
                cur_list.remove(instance_dict)
        b_succ= False
        try:
            response = self.dynamodb_client.update_item(
                TableName=self.dynamodb_table_name,
                Key={
                    'Category': {
                        'S': 'asg_instances',
                    }
                },
                AttributeUpdates={
                    'instance_list': {
                        'Value': {
                            'L': cur_list
                        }
                    }
                })
            b_succ = True
        except Exception as err:
            self.logger.error(f"Could not remove instance ID to Dynamo DB table: {err}")
        return b_succ

# FortiGate auto-scaling primary ip
    def get_primary(self):
        self.logger.info("Get primary instance information.")
        primary_instance_id = None
        primary_ip = None
        try:
            response = self.dynamodb_client.get_item(
                TableName=self.dynamodb_table_name,
                Key={
                    'Category': {
                        'S': 'primary_instance',
                    }
                },
                AttributesToGet=[
                    'primary_instance_id',
                    'primary_ip'
                ])
            items = response.get("Item")
            if items:
                primary_instance_id = items.get('primary_instance_id').get('S') if items.get('primary_instance_id') else None
                primary_ip = items.get('primary_ip').get('S') if items.get('primary_ip') else None
        except Exception as err:
            self.logger.error(f"Could not get primary instance information: {err}")
        return primary_instance_id, primary_ip

    def update_primary(self, instance_id, primary_ip):
        self.logger.info("Update primary instance infomation.")
        b_succ= False
        try:
            response = self.dynamodb_client.update_item(
                TableName=self.dynamodb_table_name,
                Key={
                    'Category': {
                        'S': 'primary_instance',
                    }
                },
                AttributeUpdates={
                    'primary_instance_id': {
                        'Value': {
                            'S': f'{instance_id}'
                        },
                        'Action': 'PUT'
                    },
                    'primary_ip': {
                        'Value': {
                            'S': f'{primary_ip}'
                        },
                        'Action': 'PUT'
                    }
                })
            b_succ = True
        except Exception as err:
            self.logger.error(f"Could not update primary instance information: {err}")
        return b_succ
    
    def check_primary(self, fgt_vm_id):
        self.logger.info(f"Check and update primary record in Dynamo DB.")
        # FortiGate instance auto-scaling configuration
        primary_instance_id, primary_ip = self.get_primary()
        if not primary_instance_id or primary_instance_id == fgt_vm_id:
            fgt_port = ""
            if self.fgt_login_port_number:
                fgt_port = ":" + self.fgt_login_port_number
            # Get next primary instance
            instance_detail = self.ec2_client.describe_instances(Filters=[
                                    {
                                        'Name': 'instance-state-name',
                                        'Values': [
                                            'running',
                                        ]
                                    }
                                ])
            self.logger.info(f"Instance detail: {instance_detail}")
            running_instance_dict = {}
            for reservation in instance_detail['Reservations']:
                for instance in reservation['Instances']:
                    cur_vm_id = instance.get('InstanceId')
                    running_instance_dict[cur_vm_id] = instance
            b_succ = False
            fgt_instanceid_list_dict = self.get_asg_instance_list_dydb()
            fgt_instanceid_list = []
            for instance_dict in fgt_instanceid_list_dict:
                fgt_instanceid_list.extend(instance_dict.values())
            for cur_vm_id in fgt_instanceid_list:
                if cur_vm_id not in running_instance_dict:
                    continue
                instance = running_instance_dict[cur_vm_id]
                fgt_vm_id = cur_vm_id
                self.fgt_primary_ip, self.fgt_primary_port = self.get_primary_ip(instance)
                fgt_private_ip = self.get_private_ip(instance)
                if not fgt_private_ip:
                    self.logger.info(f"Can not find private IP for instance: {fgt_vm_id}")
                    continue
                # Update FortiGate instance configuration
                temp_str = f"""
                config system auto-scale
                    set status enable
                    set sync-interface "{self.fgt_primary_port}"
                    set role primary
                    set psksecret "{self.fgt_system_autoscale_psksecret}"
                end
                """
                config_content = re.sub(r"([\n ])\1*", r"\1", temp_str)
                b_succ = self.upload_config(config_content, fgt_private_ip)
                if b_succ:
                    self.update_tags(
                        [fgt_vm_id], 
                        [{
                            'Key': 'Autoscale Role',
                            'Value': 'Primary'
                        }]
                    )
                    break
                else:
                    self.logger.error(f"Could not http connect to FortiGate {fgt_private_ip}")
                    continue

            # Update primary track Dynamo DB
            if b_succ:
                self.update_primary(fgt_vm_id, self.fgt_primary_ip)
            else:
                self.update_primary("", "")

            # Update secondary FortiGate instance configuration
            secondary_resource_list = []
            for cur_vm_id, instance in running_instance_dict.items():
                if cur_vm_id not in fgt_instanceid_list or cur_vm_id == fgt_vm_id:
                    continue
                cur_private_ip = self.get_private_ip(instance)
                if not cur_private_ip:
                    self.logger.info(f"Can not find private IP for instance: {fgt_vm_id}")
                    continue
                # Update FortiGate instance configuration
                temp_str = f"""
                config system auto-scale
                    set status enable
                    set sync-interface "{self.fgt_primary_port}"
                    set role secondary
                    set primary-ip {self.fgt_primary_ip}
                    set psksecret "{self.fgt_system_autoscale_psksecret}"
                end
                """
                config_content = re.sub(r"([\n ])\1*", r"\1", temp_str)
                b_succ = self.upload_config(config_content, cur_private_ip)
                if b_succ:
                    secondary_resource_list.append(cur_vm_id)
                else:
                    self.logger.error(f"Could not update system auto-scale for FortiGate {cur_vm_id}")

            self.update_tags(
                secondary_resource_list, 
                [{
                    'Key': 'Autoscale Role',
                    'Value': 'Secondary'
                }]
            )

# FortiGate configuration
    def gen_config_content(self, fgt_vm_id):
        gwlb_ips = json.loads(os.getenv('gwlb_ips'))
        user_conf = os.getenv('user_conf')
        user_conf_s3 = json.loads(os.getenv('user_conf_s3'))
        fgt_multi_vdom = os.getenv('fgt_multi_vdom') == 'true'
        create_geneve_for_all_az = os.getenv('create_geneve_for_all_az') == 'true'
        az_name_map = json.loads(os.getenv('az_name_map'))
        rst = ""
        # Geneve tunnel
        for intf_name, intf_conf in self.intf_setting.items():
            vdom = intf_conf.get("vdom", "root")
            if fgt_multi_vdom:
                rst += f"config vdom\nedit {vdom}\n"
            
            if intf_conf.get("to_gwlb") and gwlb_ips:
                az_list = intf_conf["subnet_id_map"].keys() if create_geneve_for_all_az else [self.fgt_az]
                for az_name in az_list:
                    subnet_id = intf_conf["subnet_id_map"].get(az_name)
                    if not subnet_id:
                        self.logger.error(f"Could not get the Subnet ID of AZ: {az_name}")
                        if fgt_multi_vdom:
                            rst += f"end\n"
                        continue
                    gwlb_ip = gwlb_ips.get(subnet_id)
                    if not gwlb_ip:
                        self.logger.error(f"Could not get the GWLB ip for subnet: {subnet_id}")
                        if fgt_multi_vdom:
                            rst += f"end\n"
                        continue
                    
                    intf_device_index = intf_conf.get("device_index")
                    geneve_name = az_name
                    if az_name in az_name_map:
                        geneve_name = az_name_map[az_name]
                    temp_str = f"""
                    config system geneve
                        edit {geneve_name}
                            set interface port{intf_device_index + 1}
                            set type ppp
                            set remote-ip {gwlb_ip}
                        next
                    end
                    config router static
                        edit 0
                            set dst {gwlb_ip}/32
                            set device port{intf_device_index + 1}
                            set dynamic-gateway enable
                        next
                    end
                    """
                    rst += re.sub(r"([\n ])\1*", r"\1", temp_str)

                if fgt_multi_vdom:
                    rst += f"end\n"
        # User configuration
        if user_conf:
            rst += user_conf
            rst += "\n"
        
        if user_conf_s3:
            for bucket_name, key_list in user_conf_s3.items():
                for key_name in key_list:
                    cur_user_conf = self.get_s3_file_content(bucket_name, key_name)
                    if cur_user_conf:
                        rst += cur_user_conf
                        rst += "\n"

        # FortiGate instance auto-scaling configuration
        if self.enable_fgt_system_autoscale:
            primary_instance_id, primary_ip = self.get_primary()
            if not primary_instance_id:
                self.update_primary(fgt_vm_id, self.fgt_primary_ip)
                primary_instance_id = fgt_vm_id
                primary_ip = self.fgt_primary_ip
            autoscale_role = "Primary"
            if primary_instance_id == fgt_vm_id:
                temp_str = f"""
                config system auto-scale
                    set status enable
                    set sync-interface "{self.fgt_primary_port}"
                    set role primary
                    set psksecret "{self.fgt_system_autoscale_psksecret}"
                end
                """
            else:
                autoscale_role = "Secondary"
                temp_str = f"""
                config system auto-scale
                    set status enable
                    set sync-interface "{self.fgt_primary_port}"
                    set role secondary
                    set primary-ip {primary_ip}
                    set psksecret "{self.fgt_system_autoscale_psksecret}"
                end
                """
            rst += re.sub(r"([\n ])\1*", r"\1", temp_str)
            self.update_tags(
                [fgt_vm_id], 
                [{
                    'Key': 'Autoscale Role',
                    'Value': autoscale_role
                }]
            )
        return rst

    def upload_config(self, config_content, fgt_private_ip):
        self.logger.info("Upload configuration to FortiGate instance.")
        payload = {
            "private_ip" : fgt_private_ip,
            "operation" : "upload_config",
            "parameters" : {
                "config_content": config_content
            }
        }
        b_succ = self.invoke_lambda(payload, "Event")
        return b_succ

    def get_s3_file_content(self, bucket_name, key_name):
        self.logger.info(f"Get S3 object content of bucket: {bucket_name}, key_name: {key_name}.")
        s3_file_content = ""
        try:
            response = self.s3_client.get_object(
                Bucket=bucket_name,
                Key=key_name
            )
            s3_file_content = response.get("Body").read().decode('utf-8') 
        except ClientError as e:
            self.logger.error(f"Could not get S3 object: {e}")
        return s3_file_content

    def change_password(self, fgt_private_ip, fgt_vm_id):
        self.logger.info("Change password.")
        payload = {
            "private_ip" : fgt_private_ip,
            "operation" : "change_password",
            "parameters" : {
                "fgt_vm_id": fgt_vm_id
            }
        }
        b_succ = self.invoke_lambda(payload)
        return b_succ
 
def lambda_handler(event, context):
    ## Network Interface operations
    intfObject = NetworkInterface()
    intfObject.main(event)

    ## FortiGate configuration operations
    fgtObject = FgtConf(event)
    fgtObject.main()

    return {}