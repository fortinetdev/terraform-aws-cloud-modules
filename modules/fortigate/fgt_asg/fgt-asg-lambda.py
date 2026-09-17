import os
import json
import logging
import time
import requests
import re
import uuid
import base64

import boto3
import botocore
from botocore.exceptions import ClientError
from botocore.config import Config

class Helper:
    def set_to_list(input_content):
        if not input_content:
            return
        input_type = type(input_content)
        if input_type in [str, int, bool]:
            return
        elif input_type is list:
            for i in range(len(input_content)):
                item = input_content[i]
                if type(item) is set:
                    item = list(item)
                    input_content[i] = item
                Helper.set_to_list(item)
        elif input_type is dict:
            for k, v in input_content.items():
                if type(v) is set:
                    v = list(v)
                    input_content[k] = v
                Helper.set_to_list(v)

class NetworkInterface:
    def __init__(self, logger, fgt_vm_id=""):
        self.logger = logger
        self.ec2_client = boto3.client("ec2")
        self.s3_client = boto3.client("s3")
        self.s3_bucket_name = os.getenv("lic_s3_name")
        self.intf_track_file_name = "intf_track.json"
        self.fgt_vm_id = fgt_vm_id

    def set_vm_id(self, vm_id):
        self.fgt_vm_id = vm_id
        self.instance_detail = self.ec2_client.describe_instances(InstanceIds=[self.fgt_vm_id])
        self.fgt_vm_intfs = {}
        if self.instance_detail and len(self.instance_detail['Reservations']) > 0 and len(self.instance_detail['Reservations'][0]['Instances']) > 0:
            for intf in self.instance_detail['Reservations'][0]['Instances'][0]['NetworkInterfaces']:
                cur_device_index = str(intf.get("Attachment").get("DeviceIndex"))
                self.fgt_vm_intfs[cur_device_index] = intf

    def main(self, detail_type):
        self.logger.info(f"Do interface config")

        if detail_type == "EC2 Instance-launch Lifecycle Action":
            # The launch outcome: "success", "degraded" (only the optional
            # parts failed) or "failed" (a required interface is missing).
            return self.do_launch()
        elif detail_type == "EC2 Instance-terminate Lifecycle Action":
            self.do_terminate()
            return "skipped" # do nothing
        if detail_type == "EC2 Instance Launch Successful":
            self.save_intf()
            return "skipped" # do nothing
        else:
            self.logger.info(f"Can not identify detail-type: {detail_type}")
            return "skipped" # do nothing

    def do_launch(self):
        self.logger.info(f"Do launch fgt vm instance: {self.fgt_vm_id}")
        intf_setting = json.loads(os.getenv('network_interfaces'))
        fgt_az = self.instance_detail['Reservations'][0]['Instances'][0]['Placement']['AvailabilityZone']
        outcome = "success"
        for intf_name, intf_conf in intf_setting.items():
            # Ignore if the interface already exist
            if str(intf_conf["device_index"]) in self.fgt_vm_intfs:
                continue
            # A critical interface failure fails the launch: the instance can
            # not work without it. A non-critical (additional) interface
            # failure does not block the launch, the instance runs without it
            # and its configuration is skipped by the configuration generation.
            intf_critical = intf_conf.get("critical", False)
            # Create interface
            cur_intf_id = self.create_interface(intf_name, intf_conf, fgt_az)
            if cur_intf_id == None:
                if intf_critical:
                    # Could not create the interface, the instance can not work without it
                    return "failed"
                self.logger.error(f"Could not create the non-critical interface: {intf_name}, continue without it.")
                continue
            # Attach the interface to FortiGate VM instance
            attach_id = self.attach_intf(cur_intf_id, intf_conf["device_index"])
            if attach_id == None:
                # Clean up the interface which failed to attach
                self.delete_interface(cur_intf_id)
                if intf_critical:
                    # The attach failure itself marks the launch failed
                    return "failed"
                self.logger.error(f"Could not attach the non-critical interface: {intf_name}, continue without it.")
                continue
            self.set_delete_on_termination(cur_intf_id, attach_id)
            # Create and associate Public IP if needed.
            # The public IP is optional (e.g. for manually checking the FGT instance
            # on a non-port1 interface), the association failure only degrades
            # the launch, like when reaching the AWS public IP limitation.
            if "enable_public_ip" in intf_conf and intf_conf["enable_public_ip"] :
                if self.associate_pub_ip(cur_intf_id, intf_conf) == None:
                    outcome = "degraded"
        self.logger.info(f"Configured network interfaces for instance: {self.fgt_vm_id}")
        return outcome

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
        return "success"

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
        sg_allow_lambda = os.getenv('sg_allow_lambda')
        mgmt_intf_index = os.getenv("mgmt_intf_index")
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
            security_groups = intf_conf.get("security_groups", [])
            if mgmt_intf_index and mgmt_intf_index == intf_conf.get("device_index", ""):
                security_groups.append(sg_allow_lambda)
            intf = self.ec2_client.create_network_interface(
                Description        = intf_conf["description"] if "description" in intf_conf else "",
                SubnetId           = subnet_id, 
                Groups             = security_groups,
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

class FgtConf:
    def __init__(self, logger, fgt_vm_id=""):
        self.logger = logger
        self.ec2_client = boto3.client("ec2")
        self.s3_client = boto3.client("s3")
        self.lambda_client = boto3.client(
            "lambda",
            config=Config(
                read_timeout=100     # seconds to wait for response
            )
        )

        self.logger.info(f"Do FGT config.")
        self.fgt_vm_id = fgt_vm_id
        self.cookie = {}
        self.lock_id = ""
        # DynamoDB lock: lock id is generated once per event (object level), shared by all locked categories
        self.dydb_lock_id = str(uuid.uuid1())
        self.locked_category_list = []
        self.lic_track_file_name = "asg-fgt-lic-track.json"
        self.s3_bucket_name = os.getenv("lic_s3_name")
        self.need_license = os.getenv("need_license") == "true"
        self.enable_privatelink_dydb = os.getenv("enable_privatelink_dydb") == "true"
        self.fmg_integration = json.loads(os.getenv("fmg_integration"))
        self.fgt_lic_mgmt = self.fmg_integration.get("fgt_lic_mgmt", "") if self.fmg_integration else ""
        if self.fmg_integration and self.fmg_integration.get("ums", {}):
            self.fgt_lic_mgmt = "fmg"
        if not self.enable_privatelink_dydb:
            self.dynamodb_client = boto3.client(
                "dynamodb",
                config=Config(
                    read_timeout=10     # seconds to wait for response
                )
            )
            self.dynamodb_table_name = os.getenv("dynamodb_table_name")
        self.enable_fgt_system_autoscale = os.getenv("enable_fgt_system_autoscale") == "true"
        self.fgt_system_autoscale_psksecret = os.getenv("fgt_system_autoscale_psksecret")
        self.fgt_login_port_number = os.getenv("fgt_login_port_number")
        self.internal_lambda_name = os.getenv("internal_lambda_name")
        self.mgmt_intf_index = os.getenv("mgmt_intf_index")
        self.asg_name = os.getenv("asg_name")
        self.primary_scalein_protection = os.getenv("primary_scalein_protection") == "true"
        # The environment variable can be the JSON string "null" when the
        # module variable is not set (jsonencode(null) = "null"), so the
        # loaded value can be None despite the "{}" fallback above.
        self.primary_election = json.loads(os.getenv("primary_election") or "{}") or {}
        # Map license type to the AWS marketplace product code of the FortiGate AMI,
        # used to check which license type a candidate instance belongs to.
        # Same "null" JSON string pitfall as primary_election above.
        self.license_product_code_map = json.loads(os.getenv("license_product_code_map") or "{}") or {}
        self.health_check_port = os.getenv("health_check_port")
        self.health_check_protocol = os.getenv("health_check_protocol")
        self.configid_list = json.loads(os.getenv("fortiflex_configid_list"))
        self.configname_list = json.loads(os.getenv("fortiflex_configname_list"))

    def set_vm_id(self, vm_id):
        self.fgt_vm_id = vm_id

    def main(self, detail_type):
        self.check_dydb_table_exist()
        if detail_type == "EC2 Instance-launch Lifecycle Action":
            return self.do_launch()
        elif detail_type == "EC2 Instance-terminate Lifecycle Action":
            self.do_terminate()
            return "skipped" # do nothing
        else:
            self.logger.debug(f"Can not identify detail-type: {detail_type}")
            return "skipped" # do nothing

    def check_dydb_table_exist(self):
        # Check whether the DynamoDB track table exists.
        self.logger.info("Check whether the DynamoDB track table exists.")
        if self.enable_privatelink_dydb:
            payload = {
                "service" : "dynamodb",
                "operation" : "check_table",
                "parameters" : {}
            }
            b_succ, rst = self.invoke_lambda(payload, "fgt")
            # The public lambda has no table name in the privatelink mode,
            # the internal lambda reports its own table name along.
            b_exist = rst.get("table_exist", False) if b_succ else None
            table_name = rst.get("table_name", "") if b_succ else ""
        else:
            table_name = self.dynamodb_table_name
            try:
                self.dynamodb_client.describe_table(TableName=self.dynamodb_table_name)
                b_exist = True
            except botocore.exceptions.ClientError as e:
                if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                    b_exist = False
                else:
                    # Could not determine (throttling, network, permission):
                    # stay silent here, the following operations log their own
                    # errors if the table is really missing.
                    self.logger.info(f"Could not check the DynamoDB table: {e}")
                    return
            except Exception as err:
                self.logger.info(f"Could not check the DynamoDB table: {err}")
                return
        if b_exist is False:
            self.logger.warning(
                f"The DynamoDB table {table_name} does not exist. "
                "The FortiGate ASG can not work without its track table. "
                "If this ASG shares the table with another ASG (e.g. hybrid BYOL + on-demand mode), "
                "the table owner ASG creates the table with the module_prefix prepended to dynamodb_table_name "
                "(e.g. \"pfx-fgt_asg_track_table\" with prefix \"pfx-\"), so set dynamodb_table_name of this ASG "
                "to the full table name including the prefix."
            )

    def do_launch(self):
        self.logger.info("Do launch event.")
        instance_detail = self.ec2_client.describe_instances(InstanceIds=[self.fgt_vm_id])
        # Add name for the instance
        self.update_tags(
            [self.fgt_vm_id],
            [{
                'Key': 'Name',
                'Value': self.asg_name
            }]
        )
        # Get private IP. The management ENI is attached by this Lambda and is
        # eventually-consistent in describe_instances; on fully private
        # deployments the first lookup can race the attachment and return None.
        # Retry with a bounded wait before giving up so the ENI (and its
        # PrivateIpAddress) has time to become visible.
        fgt_private_ip = self.get_private_ip(instance_detail['Reservations'][0]['Instances'][0])
        if not fgt_private_ip:
            for _attempt in range(12):  # up to ~12 * 5s = 60s
                self.logger.info(f"Management ENI private IP not visible yet (attempt {_attempt + 1}); waiting for eventual consistency")
                time.sleep(5)
                try:
                    _inst = self.ec2_client.describe_instances(
                        InstanceIds=[self.fgt_vm_id]
                    )['Reservations'][0]['Instances'][0]
                except Exception as _err:
                    self.logger.info(f"describe_instances retry failed: {_err}")
                    continue
                fgt_private_ip = self.get_private_ip(_inst)
                if fgt_private_ip:
                    break
        if not fgt_private_ip:
            self.logger.error("Can not find private IP after retries.")
            return "failed"
        # Change password
        if self.fgt_lic_mgmt != "fmg":
            b_succ = self.change_password(fgt_private_ip, self.fgt_vm_id)
            if not b_succ:
                self.logger.error(f"Change password failed.")
                return "failed"

        # Update in Dynamo DB. The registration makes the instance visible to
        # the terminate cleanup and the primary election, a failure degrades
        # the launch but the instance itself still works, so it does not fail
        # the launch.
        b_dydb = self.add_asg_instance_dydb(self.fgt_vm_id)
        if not b_dydb:
            self.logger.warning("Could not register the instance in Dynamo DB, continue without the track record.")

        # Upload license
        if self.need_license and self.fgt_lic_mgmt != "fmg":
            # Update Serial numbers
            b_succ = self.update_all_sn_list()
            # The license activation can fail transiently: a token generated
            # right after a serial number reactivation may not be valid on
            # FortiGuard yet, and a FortiGate just up from boot may reject the
            # first token. Observed in the field: the same serial number
            # succeeded on the next attempt seconds later. Retry before giving
            # up, an instance without an active license gets no configuration
            # at all, so it joins the cluster with no role set.
            lic_retry_max = 3
            for lic_retry in range(lic_retry_max):
                b_succ = self.upload_license(fgt_private_ip, self.fgt_vm_id)
                if b_succ:
                    break
                if lic_retry < lic_retry_max - 1:
                    time.sleep(20)
            if not b_succ:
                return "failed"

        # Configure the FortiGate instance
        # Initiate as success: when fgt_lic_mgmt is "fmg", FortiGate Manager
        # pushes the license and configuration, the following block is skipped
        # and there is no upload result to report.
        b_succ = True
        if self.fgt_lic_mgmt != "fmg":
            time.sleep(10)
            self.intf_setting = json.loads(os.getenv('network_interfaces'))
            self.fgt_az = instance_detail['Reservations'][0]['Instances'][0]['Placement']['AvailabilityZone']
            self.fgt_primary_ip, self.fgt_primary_port = self.get_primary_ip(instance_detail['Reservations'][0]['Instances'][0])

            config_content = self.gen_config_content(self.fgt_vm_id)
            if config_content is None:
                # None marks the configuration generation failed, e.g. the
                # primary_instance record could not be locked, the instance
                # would run without its auto-scale role configuration.
                self.logger.error("Could not generate the configuration content.")
                return "failed"
            b_succ = self.upload_config(config_content, fgt_private_ip)
        if not b_succ:
            return "failed"
        return "success"


    def do_terminate(self):
        self.logger.info("Do terminate event.")
        # Upload license
        if self.need_license and self.fgt_lic_mgmt != "fmg":
            # Update Serial numbers
            b_succ = self.update_all_sn_list()
            # Update license record
            b_updated = self.release_lic(self.fgt_vm_id)
            if not b_updated:
                # Get oauth token outside the lock since it may take seconds when token expired
                oauth_token = self.get_fortiflex_oauth_token()
                if not oauth_token:
                    self.logger.error("Could not get valid OAuth token, skip release license record.")
                else:
                    # Lock fortiflex category for the used_sn_map restore: the SN must be
                    # moved from used to available atomically. stop_sn is kept inside the
                    # lock: if the SN were restored but stopped outside the lock, a concurrent
                    # launch could pick the restored SN and activate it before stop_sn deactivates it.
                    b_locked = self.lock_dydb("fortiflex")
                    if b_locked:
                        try:
                            used_sn_map = self.get_used_sn_map()
                            if self.fgt_vm_id in used_sn_map:
                                sn = used_sn_map.pop(self.fgt_vm_id)
                                self.update_used_sn_map(used_sn_map)
                                self.add_available_sn({sn})
                                # Deactive current token
                                self.stop_sn(sn, oauth_token)
                        finally:
                            self.unlock_dydb("fortiflex")
                    else:
                        self.logger.error("Could not lock fortiflex in Dynamo DB, skip release license record.")
        # Update instance info on Dynamo DB
        self.remove_asg_instance_dydb(self.fgt_vm_id)
        if self.enable_fgt_system_autoscale:
            instance_detail = self.ec2_client.describe_instances(InstanceIds=[self.fgt_vm_id])
            if instance_detail['Reservations'] and instance_detail['Reservations'][0]['Instances']:
                self.update_tags(
                    [self.fgt_vm_id], 
                    [{
                        'Key': 'Autoscale Role',
                        'Value': ''
                    }]
                )
            self.check_primary(self.fgt_vm_id)
        return "success"

# Instance information
    def get_private_ip(self, instance):
        rst = None
        if not rst:
            for intf in instance['NetworkInterfaces']:
                if "Attachment" not in intf or str(intf["Attachment"].get("DeviceIndex")) != self.mgmt_intf_index:
                    continue
                if "PrivateIpAddress" not in intf:
                    continue
                cur_private_ip = intf.get("PrivateIpAddress")
                if cur_private_ip:
                    rst = cur_private_ip
                    break
        return rst

    def get_primary_ip(self, instance):
        self.logger.info(f"Get primary ip for current instance.")
        hi_p_ip = ""
        hi_p_port = ""
        hi_index = -1
        # Track the management interface (device_index == mgmt_intf_index) as a
        # fallback for deployments where no interface has an EIP association
        # (e.g. fully private fleets). Without this, the block below falls back
        # to instance.PrivateIpAddress / port1, which on such deployments is the
        # data-plane interface (e.g. the GWLB/GENEVE interface), so the autoscale
        # sync-interface and the recorded primary-ip end up on the wrong
        # interface and primary->secondary configuration sync fails.
        mgmt_p_ip = ""
        mgmt_p_port = ""
        interfaces = instance.get("NetworkInterfaces")
        if not interfaces:
            self.logger.error(f"Could not get network instances.")
            return hi_p_ip, hi_p_port
        for interface in interfaces:
            p_ip = interface.get("PrivateIpAddress")
            d_index = interface.get("Attachment").get("DeviceIndex")
            p_port = f"port{d_index + 1}"
            if self.mgmt_intf_index and str(d_index) == self.mgmt_intf_index:
                mgmt_p_ip = p_ip
                mgmt_p_port = p_port
            if "Association" not in interface:
                continue
            if d_index > hi_index:
                hi_p_ip = p_ip
                hi_p_port = p_port
                hi_index = d_index
        if not hi_p_ip:
            if mgmt_p_ip:
                hi_p_ip = mgmt_p_ip
                hi_p_port = mgmt_p_port
            else:
                hi_p_ip = instance.get('PrivateIpAddress')
                hi_p_port = "port1"
        return hi_p_ip, hi_p_port

# Invoke lambda function
    def invoke_lambda(self, payload, target_lambda, invocation_type=""):
        b_succ= False
        rst = {}
        if target_lambda == "fgt":
            fucnName = self.internal_lambda_name
        else:
            self.logger.error(f"Unknown target lambda function name: {target_lambda}")
            return
        if invocation_type == "":
            invocation_type = 'RequestResponse'
        try:
            Helper.set_to_list(payload)
            response = self.lambda_client.invoke(
                FunctionName = fucnName,
                InvocationType = invocation_type,
                Payload = json.dumps(payload)
            )
            if "StatusCode" in response and response["StatusCode"] in [200, 202, 204]:
                b_succ = True
                payload_contant = response["Payload"].read()
                if payload_contant:
                    payload_contant_json = json.loads(payload_contant.decode("utf-8"))
                    if payload_contant_json["ErrorMsg"]:
                        self.logger.error("Invoke lambda function response error msg: {}".format(payload_contant_json["ErrorMsg"]))
                        b_succ = False
                    else:
                        rst = payload_contant_json["ResponseContent"]
            else:
                errmsg = ""
                if "FunctionError" in response:
                    errmsg = response["FunctionError"]
                self.logger.error(f"Invoke lambda function failed: {errmsg}")
        except Exception as err:
            self.logger.error(f"Could not invoke lambda function, error: {err}")
        return b_succ, rst
    
# License
    def upload_license(self, fgt_private_ip, fgt_vm_id):
        # Get license, license_type: "token", "file"; license_content：token if license_type is token, file name if license_type is file
        self.logger.info("Upload license.")
        license_type, license_content, sn_or_file_name = self.get_license(fgt_vm_id)
        if license_type == "":
            self.logger.error(f"Could not get license!")
            return False

        # Upload license
        if license_type == "token":
            payload = {
                "service" : "fgt_vm",
                "operation" : "upload_license",
                "parameters" : {
                    "private_ip" : fgt_private_ip,
                    "license_type": license_type,
                    "license_content": license_content
                }
            }
            b_succ, response = self.invoke_lambda(payload, "fgt")
            # Lock fortiflex category for the used_sn_map update or SN restore.
            # The license upload above takes long time, keep it outside the lock.
            b_locked = self.lock_dydb("fortiflex")
            if not b_locked:
                self.logger.error("Could not lock fortiflex in Dynamo DB after license upload.")
                return False
            try:
                if b_succ:
                    used_sn_map = self.get_used_sn_map()
                    used_sn_map[fgt_vm_id] = sn_or_file_name
                    self.update_used_sn_map(used_sn_map)
                else:
                    self.add_available_sn({sn_or_file_name})
                    self.logger.error("Could not activate the token on FortiGate instance.")
            finally:
                self.unlock_dydb("fortiflex")
        elif license_type == "file":
            lic_file_content = self.get_lic_file_content(license_content)
            payload = {
                "service" : "fgt_vm",
                "operation" : "upload_license",
                "parameters" : {
                    "private_ip" : fgt_private_ip,
                    "license_type": license_type,
                    "license_content": lic_file_content
                }
            }
            b_succ, response = self.invoke_lambda(payload, "fgt")
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
        # Lock fortiflex category for the read-claim-write of the available SN.
        # The reactivate and token generation must stay inside the lock to reserve the
        # SN, otherwise two concurrent launches could pick the same SN.
        b_locked = self.lock_dydb("fortiflex")
        if not b_locked:
            self.logger.error("Could not lock fortiflex in Dynamo DB, could not get license token.")
            return "", "", ""
        # Get serial number and generate vm token
        license_type = ""
        license_content = ""
        sn_or_file_name = ""
        try:
            dydb_items = self.get_item_from_dydb("fortiflex", ["available_sn_list"])
            available_sn_list = dydb_items.get("available_sn_list", [])
            if available_sn_list:
                for cur_sn in available_sn_list:
                    b_succ = self.reactivate_sn(cur_sn, oauth_token)
                    if not b_succ:
                        continue
                    vm_token = self.generate_vm_token(cur_sn, oauth_token)
                    if vm_token:
                        self.remove_available_sn({cur_sn})
                        license_type = "token"
                        license_content = vm_token
                        sn_or_file_name = cur_sn
                        break
            else:
                self.logger.info("Could not get available serial number.")
        finally:
            self.unlock_dydb("fortiflex")
        if license_type:
            return license_type, license_content, sn_or_file_name

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
        self.logger.info("Release license.")
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
        self.logger.info("Get FortiFlex OAuth token.")
        dydb_items = self.get_item_from_dydb("fortiflex", ["oauth_token"])
        oauth_token = dydb_items.get("oauth_token", "")
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
            if oauth_refresh_token: # Generate OAuth token by given refresh token
                new_oauth_token = self.refresh_oauth_token(oauth_refresh_token)
            if not new_oauth_token: # Try FortiFlex API username and password if refresh token not been provided or invalid
                new_oauth_token, new_refresh_token = self.generate_refresh_token()
                
        return new_oauth_token

    def update_fortiflex_oauth_token(self, oauth_token):
        b_succ = self.put_item_to_dydb("fortiflex", "oauth_token", oauth_token)
        return b_succ

    def get_fortiflex_refresh_token(self):
        dydb_items = self.get_item_from_dydb("fortiflex", ["oauth_refresh_token"])
        oauth_refresh_token = dydb_items.get("oauth_refresh_token", "")
        return oauth_refresh_token

    def update_fortiflex_refresh_token(self, oauth_refresh_token):
        b_succ = self.put_item_to_dydb("fortiflex", "oauth_refresh_token", oauth_refresh_token)
        return b_succ
    
    def generate_refresh_token(self):
        self.logger.info("Generate OAuth token and refresh token by API username and password.")
        oauth_token = ""
        refresh_token = ""
        fortiflex_username = os.getenv("fortiflex_username")
        fortiflex_password = os.getenv("fortiflex_password")
        if not fortiflex_username or not fortiflex_password:
            return oauth_token, refresh_token
        
        url = "https://customerapiauth.fortinet.com/api/v1/oauth/token/"
        header = {
            "Content-Type": "application/json"
        }
        body = {
            "username": fortiflex_username,
            "password": fortiflex_password,
            "client_id": "flexvm",
            "grant_type":"password"
        }
        response = requests.post(url, headers=header, json=body, verify=False, timeout=10)
        if response.status_code == 200:
            response_json = response.json()
            if response_json:
                if "access_token" in response_json and "refresh_token" in response_json:
                    oauth_token = response_json["access_token"]
                    refresh_token = response_json["refresh_token"]
                    self.update_fortiflex_oauth_token(oauth_token)
                    self.update_fortiflex_refresh_token(refresh_token)
            else:
                self.logger.info("Could not get http return status")
        response.close()
        return oauth_token, refresh_token
    
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
   
    def reactivate_sn(self, sn, oauth_token):
        self.logger.info("Reactivate Serial Number License.")
        b_succ = False
        url = "https://support.fortinet.com/ES/api/fortiflex/v2/entitlements/reactivate"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {oauth_token}"
        }
        body = {
            "serialNumber": sn
        }
        response = requests.post(url, headers=header, json=body, verify=False, timeout=10)
        response_json = response.json()
        if response.status_code == 200:
            if response_json:
                if "entitlements" not in response_json or not response_json["entitlements"]:
                    if "error" in response_json and not response_json["error"]:
                        err_msg = response_json["error"]
                        self.logger.error(f"Could not reactivate the license for serial number {sn}, error msg: {err_msg}")
                elif "status" in response_json and response_json["status"] == 0 :
                    b_succ = True
            else:
                self.logger.info("Could not get http return status")
        elif response.status_code == 400:
            # return True if SN's status is 'PENDING' and could not be modified
            if "status" in response_json and response_json["status"] == -1:
                b_succ = True
        response.close()
        return b_succ
   
    def stop_sn(self, sn, oauth_token):
        self.logger.info(f"Stop Serial Number: {sn}.")
        b_succ = True
        url = "https://support.fortinet.com/ES/api/fortiflex/v2/entitlements/stop"
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
                        self.logger.error(f"Could not stop the license for serial number {sn}, error msg: {err_msg}")
                    b_succ = False
            else:
                self.logger.info("Could not get http return status")
                b_succ = False
        response.close()
        return b_succ

   # Serial number related
    def update_all_sn_list(self):
        self.logger.info("Update all serial number list")
        # get SN list given by user
        config_sn_list = json.loads(os.getenv("fortiflex_sn_list"))
        if not config_sn_list:
            config_sn_list = []
        # get config ID list given by user, and get all available SNs under the config IDs
        configid_list_total = []
        if self.configid_list:
            configid_list_total = self.configid_list
        if self.configname_list:
            configid_list_by_name = self.convert_config_name_to_id(self.configname_list)
            configid_list_total = list(set(configid_list_total) | set(configid_list_by_name))
        for configid in configid_list_total:
            cur_sn_list = self.get_sn_by_configid(configid)
            config_sn_list.extend(cur_sn_list)

        # get used SN list
        # Lock fortiflex category for the read-modify-write of SN lists.
        # The FortiFlex API collection above and the re-license upload below are outside the lock.
        b_locked = self.lock_dydb("fortiflex")
        if not b_locked:
            self.logger.error("Could not lock fortiflex in Dynamo DB, skip update all serial number list.")
            return False
        relink_instance_list = []
        try:
            used_sn_map = self.get_used_sn_map()
            used_sn_set = set(used_sn_map.values())
            config_sn_list.extend(used_sn_set)
            if not config_sn_list:
                return False
            all_sn_list = set(config_sn_list)
            self.all_sn_list = all_sn_list
            # Update all_sn_list in Dynamo DB
            dydb_all_sn_list = []
            dydb_items = self.get_item_from_dydb("fortiflex", ["all_sn_list"])
            dydb_all_sn_list = set(dydb_items.get("all_sn_list", []))
            if all_sn_list != dydb_all_sn_list:
                # Update all_sn_list
                self.put_item_to_dydb("fortiflex", "all_sn_list", all_sn_list)
            # Update available_sn_list
            new_available_sn_list = all_sn_list - used_sn_set
            removed_sn_list = dydb_all_sn_list - all_sn_list
            if new_available_sn_list:
                self.add_available_sn(new_available_sn_list)
            if removed_sn_list:
                self.remove_available_sn(removed_sn_list)
                for instance_id, sn in used_sn_map.items():
                    if sn in removed_sn_list:
                        relink_instance_list.append((instance_id, sn))
        finally:
            self.unlock_dydb("fortiflex")
        # Change license for the instances whose SN was removed. Keep it outside the lock
        # since upload license takes long time (license upload and FortiGate reboot).
        for instance_id, sn in relink_instance_list:
            self.logger.info(f"Change license for instance {instance_id}")
            instance_detail = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            cur_private_ip = self.get_private_ip(instance_detail['Reservations'][0]['Instances'][0])
            if not cur_private_ip:
                self.logger.info(f"Can not find private IP for instance: {instance_id}")
                continue
            self.upload_license(cur_private_ip, instance_id)
        return True

    def convert_config_name_to_id(self, configname_list):
        self.logger.info(f"Convert config name list to config id list: {configname_list}")
        configid_list = []
        if not configname_list:
            self.logger.info(f"configname_list is empty")
            return configid_list
        # Get config name to config id map
        configname_to_configid_map = self.get_configname_to_configid_map()
        if not configname_to_configid_map:
            self.logger.info(f"Could not get config name to config id map.")
            return configid_list
        # Generate config id list based on the map and input config name list
        for configname in configname_list:
            if configname in configname_to_configid_map:
                configid_list.append(configname_to_configid_map[configname])
            else:
                self.logger.info(f"Could not find config id for config name: {configname}")
        self.logger.info(f"Config id list: {configid_list}")
        return configid_list

    def get_configname_to_configid_map(self):
        self.logger.info("Get config name to config id map.")
        oauth_token = self.get_fortiflex_oauth_token()
        if not oauth_token:
            self.logger.info(f"Could not get valid OAuth token.")
            return {}
        # Get program serial number, which is required by configs/list API
        program_serial_number = self.get_program_serial_number(oauth_token)
        if not program_serial_number:
            self.logger.info(f"Could not get program serial number.")
            return {}
        configname_to_configid_map = {}
        url = "https://support.fortinet.com/ES/api/fortiflex/v2/configs/list"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {oauth_token}"
        }
        body = {
            "programSerialNumber": program_serial_number
        }
        response = requests.post(url, headers=header, json=body, verify=False, timeout=10)
        if response.status_code == 200:
            response_json = response.json()
            if response_json:
                if "configs" in response_json and response_json["configs"]:
                    for ele in response_json["configs"]:
                        cur_configid = ele["id"]
                        cur_configname = ele["name"]
                        configname_to_configid_map[cur_configname] = cur_configid
                else:
                    if "error" in response_json and response_json["error"]:
                        err_msg = response_json["error"]
                        self.logger.error(f"Could not get configs, error msg: {err_msg}")
            else:
                self.logger.info("Could not get http return status")
        response.close()
        return configname_to_configid_map

    def get_program_serial_number(self, oauth_token):
        self.logger.info("Get program serial number.")
        program_serial_number = ""
        url = "https://support.fortinet.com/ES/api/fortiflex/v2/programs/list"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {oauth_token}"
        }
        response = requests.post(url, headers=header, json={}, verify=False, timeout=10)
        if response.status_code == 200:
            response_json = response.json()
            if response_json:
                if "programs" in response_json and response_json["programs"]:
                    for ele in response_json["programs"]:
                        if "serialNumber" in ele and ele["serialNumber"]:
                            program_serial_number = ele["serialNumber"]
                            break
                else:
                    if "error" in response_json and response_json["error"]:
                        err_msg = response_json["error"]
                        self.logger.error(f"Could not get programs, error msg: {err_msg}")
            else:
                self.logger.info("Could not get http return status")
        response.close()
        return program_serial_number

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
                    cur_sn = ele["serialNumber"]
                    if ele["status"] in {"ACTIVE"} and ele["tokenStatus"] == "NOTUSED":
                        sn_list.append(cur_sn)
                        self.stop_sn(cur_sn, oauth_token)
                    elif ele["status"] in {"STOPPED", "PENDING"}:
                        sn_list.append(cur_sn)
            else:
                self.logger.info("Could not get http return status")
        response.close()
        return sn_list

    def get_next_available_sn(self):
        self.logger.info("Get next available serial number.")
        dydb_items = self.get_item_from_dydb("fortiflex", ["available_sn_list"])
        available_sn_list = dydb_items.get("available_sn_list", [])
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
        used_sn_map = dydb_items.get("used_sn_map", {})
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

   # Set scale-in protection
    def set_primary_scalein_protection(self, fgt_vm_id):
        self.logger.info("Set primary instance scale in protection.")
        asg_client = boto3.client("autoscaling")
        b_succ= False
        if not fgt_vm_id:
            return b_succ
        try:
            response = asg_client.set_instance_protection(
                InstanceIds=[fgt_vm_id],
                AutoScalingGroupName=self.asg_name,
                ProtectedFromScaleIn=True
            )
            b_succ = True
        except Exception as err:
            self.logger.error(f"Could not set scale-in protection for {fgt_vm_id}, error: {err}")
        return b_succ

  # AWS Dynamo DB operations
    def get_item_from_dydb(self, category, attributes):
        rst = {}
        try:
            if self.enable_privatelink_dydb:
                payload = {
                    "service" : "dynamodb",
                    "operation" : "get_item",
                    "parameters" : {
                        "category" : category,
                        "attributes": attributes
                    }
                }
                b_succ, rst = self.invoke_lambda(payload, "fgt")
            else:
                response = self.dynamodb_client.get_item(
                    TableName=self.dynamodb_table_name,
                    Key={
                        'Category': {
                            'S': category,
                        }
                    },
                    AttributesToGet=attributes)
                resp_content = response.get("Item")
                for attr_name in attributes:
                    if attr_name in resp_content:
                        rst[attr_name] = self.convert_aws_dydb_to_normal_format(resp_content[attr_name])                
        except Exception as err:
            self.logger.error(f"Could not get item from Dynamo DB table: {err}")
        return rst

    def put_item_to_dydb(self, category, attribute_name, attribute_content):
        b_succ= False
        try:
            if self.enable_privatelink_dydb:
                payload = {
                    "service" : "dynamodb",
                    "operation" : "put_item",
                    "parameters" : {
                        "category" : category,
                        "attribute_name": attribute_name,
                        "attribute_content": attribute_content,
                        "lock_id": self.dydb_lock_id if category in self.locked_category_list else ""
                    }
                }
                # Must be synchronous: the write has to complete before unlock_dydb clears the lock,
                # otherwise the write lands after the lock is released and is dropped by the condition check.
                b_succ, rst = self.invoke_lambda(payload, "fgt")
            else:
                aws_format_content = self.convert_to_aws_dydb_format(attribute_content)
                if not aws_format_content:
                    self.logger.info(f"Attribute content is empty: {attribute_content}")
                    return self.remove_item_from_dydb(category, attribute_name, attribute_content)
                # When the category is locked by current lock id, only allow the update if the lock id matches and the lock is not expired
                if category in self.locked_category_list:
                    update_expression = 'SET #attr = :val'
                    expression_attribute_names = {'#attr': attribute_name, '#lock': 'lock'}
                    expression_attribute_values = {
                        ':val': aws_format_content,
                        ':cur_lock_id': {'S': self.dydb_lock_id},
                        ':now': {'N': str(int(time.time()))}
                    }
                    response = self.dynamodb_client.update_item(
                        TableName=self.dynamodb_table_name,
                        Key={
                            'Category': {
                                'S': category,
                            }
                        },
                        UpdateExpression=update_expression,
                        ConditionExpression='#lock.lock_id = :cur_lock_id AND :now < #lock.expire_time',
                        ExpressionAttributeNames=expression_attribute_names,
                        ExpressionAttributeValues=expression_attribute_values)
                else:
                    # No ConditionExpression parameter at all: passing None raises ParamValidationError
                    response = self.dynamodb_client.update_item(
                        TableName=self.dynamodb_table_name,
                        Key={
                            'Category': {
                                'S': category,
                            }
                        },
                        UpdateExpression='SET #attr = :val',
                        ExpressionAttributeNames={'#attr': attribute_name},
                        ExpressionAttributeValues={':val': aws_format_content})
                b_succ = True
        except Exception as err:
            self.logger.error(f"Could not update item in Dynamo DB table: {err}")
        return b_succ

    def add_item_to_dydb(self, category, attribute_name, attribute_content):
        b_succ= False
        try:
            if self.enable_privatelink_dydb:
                payload = {
                    "service" : "dynamodb",
                    "operation" : "add_item",
                    "parameters" : {
                        "category" : category,
                        "attribute_name": attribute_name,
                        "attribute_content": attribute_content,
                        "lock_id": self.dydb_lock_id if category in self.locked_category_list else ""
                    }
                }
                # Must be synchronous: the write has to complete before unlock_dydb clears the lock,
                # otherwise the write lands after the lock is released and is dropped by the condition check.
                b_succ, rst = self.invoke_lambda(payload, "fgt")
            else:
                if type(attribute_content) not in [set, int, float]:
                    self.logger.error(f"Could not do the ADD operation for attribute type: {type(attribute_content)}")
                    return False
                aws_format_content = self.convert_to_aws_dydb_format(attribute_content)
                if not aws_format_content:
                    self.logger.info(f"Attribute content is empty: {attribute_content}")
                    return False
                # When the category is locked by current lock id, only allow the update if the lock id matches and the lock is not expired
                if category in self.locked_category_list:
                    update_expression = 'ADD #attr :val'
                    expression_attribute_names = {'#attr': attribute_name, '#lock': 'lock'}
                    expression_attribute_values = {
                        ':val': aws_format_content,
                        ':cur_lock_id': {'S': self.dydb_lock_id},
                        ':now': {'N': str(int(time.time()))}
                    }
                    response = self.dynamodb_client.update_item(
                        TableName=self.dynamodb_table_name,
                        Key={
                            'Category': {
                                'S': category,
                            }
                        },
                        UpdateExpression=update_expression,
                        ConditionExpression='#lock.lock_id = :cur_lock_id AND :now < #lock.expire_time',
                        ExpressionAttributeNames=expression_attribute_names,
                        ExpressionAttributeValues=expression_attribute_values)
                else:
                    # No ConditionExpression parameter at all: passing None raises ParamValidationError
                    response = self.dynamodb_client.update_item(
                        TableName=self.dynamodb_table_name,
                        Key={
                            'Category': {
                                'S': category,
                            }
                        },
                        UpdateExpression='ADD #attr :val',
                        ExpressionAttributeNames={'#attr': attribute_name},
                        ExpressionAttributeValues={':val': aws_format_content})
                b_succ = True
        except Exception as err:
            self.logger.error(f"Could not add item in Dynamo DB table: {err}")
        return b_succ

    def remove_item_from_dydb(self, category, attribute_name, attribute_content):
        b_succ= False
        try:
            if self.enable_privatelink_dydb:
                payload = {
                    "service" : "dynamodb",
                    "operation" : "remove_item",
                    "parameters" : {
                        "category" : category,
                        "attribute_name": attribute_name,
                        "attribute_content": attribute_content,
                        "lock_id": self.dydb_lock_id if category in self.locked_category_list else ""
                    }
                }
                # Must be synchronous: the write has to complete before unlock_dydb clears the lock,
                # otherwise the write lands after the lock is released and is dropped by the condition check.
                b_succ, rst = self.invoke_lambda(payload, "fgt")
            else:
                aws_format_content = self.convert_to_aws_dydb_format(attribute_content)
                if not aws_format_content:
                    self.logger.info(f"Attribute content is empty: {attribute_content}")
                    return False
                # When the category is locked by current lock id, only allow the update if the lock id matches and the lock is not expired
                if category in self.locked_category_list:
                    update_expression = 'DELETE #attr :val'
                    expression_attribute_names = {'#attr': attribute_name, '#lock': 'lock'}
                    expression_attribute_values = {
                        ':val': aws_format_content,
                        ':cur_lock_id': {'S': self.dydb_lock_id},
                        ':now': {'N': str(int(time.time()))}
                    }
                    response = self.dynamodb_client.update_item(
                        TableName=self.dynamodb_table_name,
                        Key={
                            'Category': {
                                'S': category,
                            }
                        },
                        UpdateExpression=update_expression,
                        ConditionExpression='#lock.lock_id = :cur_lock_id AND :now < #lock.expire_time',
                        ExpressionAttributeNames=expression_attribute_names,
                        ExpressionAttributeValues=expression_attribute_values)
                else:
                    # No ConditionExpression parameter at all: passing None raises ParamValidationError
                    response = self.dynamodb_client.update_item(
                        TableName=self.dynamodb_table_name,
                        Key={
                            'Category': {
                                'S': category,
                            }
                        },
                        UpdateExpression='DELETE #attr :val',
                        ExpressionAttributeNames={'#attr': attribute_name},
                        ExpressionAttributeValues={':val': aws_format_content})
                b_succ = True
        except Exception as err:
            self.logger.error(f"Could not remove item in Dynamo DB table: {err}")
        return b_succ

    def lock_dydb(self, category, lock_expire_seconds=120):
        # Already locked this category by current object, return directly to support reentrant lock
        if category in self.locked_category_list:
            return True
        b_succ = False
        expire_time = int(time.time()) + lock_expire_seconds
        if self.enable_privatelink_dydb:
            payload = {
                "service" : "dynamodb",
                "operation" : "lock_item",
                "parameters" : {
                    "category" : category,
                    "lock_id": self.dydb_lock_id,
                    "expire_time": expire_time
                }
            }
            b_succ, rst = self.invoke_lambda(payload, "fgt")
        else:
            max_loop = 60
            for i in range(max_loop):
                try:
                    response = self.dynamodb_client.update_item(
                        TableName=self.dynamodb_table_name,
                        Key={
                            'Category': {
                                'S': category,
                            }
                        },
                        UpdateExpression='SET #lock = :lock_val',
                        ConditionExpression='attribute_not_exists(#lock) OR attribute_not_exists(#lock.lock_id) OR #lock.lock_id = :empty OR :now > #lock.expire_time',
                        ExpressionAttributeNames={
                            '#lock': 'lock'
                        },
                        ExpressionAttributeValues={
                            ':lock_val': {
                                'M': {
                                    'lock_id': {'S': self.dydb_lock_id},
                                    'expire_time': {'N': str(expire_time)}
                                }
                            },
                            ':empty': {'S': ''},
                            ':now': {'N': str(int(time.time()))}
                        }
                    )
                    b_succ = True
                    break
                except botocore.exceptions.ClientError as e:
                    if e.response['Error']['Code'] == "ConditionalCheckFailedException":
                        time.sleep(2)
                        # Update expire time for next retry, lock id keep the same in object level
                        expire_time = int(time.time()) + lock_expire_seconds
                        continue
                    break
                except Exception as err:
                    self.logger.error(f"Could not lock DynamoDB: {err}")
                    break
        if b_succ:
            self.locked_category_list.append(category)
        return b_succ

    def unlock_dydb(self, category):
        b_succ = False
        # Not locked this category by current object, return directly
        if category not in self.locked_category_list:
            return True
        if self.enable_privatelink_dydb:
            payload = {
                "service" : "dynamodb",
                "operation" : "unlock_item",
                "parameters" : {
                    "category" : category,
                    "lock_id": self.dydb_lock_id
                }
            }
            b_succ, rst = self.invoke_lambda(payload, "fgt")
        else:
            try:
                response = self.dynamodb_client.update_item(
                    TableName=self.dynamodb_table_name,
                    Key={
                        'Category': {
                            'S': category,
                        }
                    },
                    UpdateExpression='SET #lock = :empty_lock',
                    ExpressionAttributeNames={
                        '#lock': 'lock'
                    },
                    ExpressionAttributeValues={
                        ':empty_lock': {
                            'M': {
                                'lock_id': {'S': ''},
                                'expire_time': {'S': ''}
                            }
                        }
                    }
                )
                b_succ = True
            except Exception as err:
                self.logger.error(f"Could not unlock DynamoDB: {err}")
        if b_succ:
            self.locked_category_list.remove(category)
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
            response = self.get_item_from_dydb("asg_instances", ["instance_list"])
            if response:
                rst = response.get('instance_list')
        except Exception as err:
            self.logger.error(f"Could not get instance list of ASG: {err}")
        return rst

    def add_asg_instance_dydb(self, instance_id):
        self.logger.info("Add instance ID to Dynamo DB table.")
        b_succ = False
        b_locked = self.lock_dydb("asg_instances")
        if not b_locked:
            self.logger.error("Could not lock asg_instances in Dynamo DB.")
            return False
        try:
            cur_list = self.get_asg_instance_list_dydb()
            for instance_dict in cur_list:
                if instance_id in instance_dict.values():
                    self.logger.info(f"Instance already in the instance list of DynamoDB: {instance_id}")
                    return True
            cur_list.append({
                'S': instance_id
            })
            b_succ = self.put_item_to_dydb("asg_instances", "instance_list", cur_list)
        except Exception as err:
            self.logger.error(f"Could not add instance ID to Dynamo DB table: {err}")
        finally:
            self.unlock_dydb("asg_instances")
        return b_succ

    def remove_asg_instance_dydb(self, instance_id):
        self.logger.info("Remove instance ID from Dynamo DB table.")
        b_succ = False
        b_locked = self.lock_dydb("asg_instances")
        if not b_locked:
            self.logger.error("Could not lock asg_instances in Dynamo DB.")
            return False
        try:
            cur_list = self.get_asg_instance_list_dydb()
            for instance_dict in cur_list:
                if instance_id in instance_dict.values():
                    cur_list.remove(instance_dict)
            b_succ = self.put_item_to_dydb("asg_instances", "instance_list", cur_list)
        except Exception as err:
            self.logger.error(f"Could not remove instance ID to Dynamo DB table: {err}")
        finally:
            self.unlock_dydb("asg_instances")
        return b_succ

    def get_instance_dict(self, state_name_list):
        self.logger.info(f"Get instance ID list with state of {state_name_list}.")
        instance_detail = self.ec2_client.describe_instances(Filters=[
                                {
                                    'Name': 'instance-state-name',
                                    'Values': state_name_list
                                }
                            ])
        running_instance_dict = {}
        for reservation in instance_detail['Reservations']:
            for instance in reservation['Instances']:
                cur_vm_id = instance.get('InstanceId')
                running_instance_dict[cur_vm_id] = instance
        return running_instance_dict
    
# FortiGate auto-scaling primary ip
    def get_primary(self):
        self.logger.info("Get primary instance information.")
        primary_instance_id = None
        primary_ip = None
        try:
            response = self.get_item_from_dydb("primary_instance", ["primary_instance_id", "primary_ip"])
            if response:
                primary_instance_id = response.get('primary_instance_id')
                primary_ip = response.get('primary_ip')
        except Exception as err:
            self.logger.error(f"Could not get primary instance information: {err}")
        return primary_instance_id, primary_ip

    def update_primary(self, instance_id, primary_ip):
        self.logger.info("Update primary instance infomation.")
        b_succ= False
        try:
            b_succ = self.put_item_to_dydb("primary_instance", "primary_instance_id", instance_id)
            b_succ = self.put_item_to_dydb("primary_instance", "primary_ip", primary_ip)
        except Exception as err:
            self.logger.error(f"Could not update primary instance information: {err}")
        return b_succ

    def is_instance_running(self, instance_id):
        # Check whether the instance still exists and is in the running state.
        # Used to detect a stale primary record: the recorded primary can be
        # terminated outside a terminate event, e.g. by deleting the ASG, so
        # no re-election ever ran and the record points at a dead instance.
        # Return True (running), False (surely not running any more) or
        # None (could not determine, e.g. an API error: caller keeps the
        # record then, a wrong clear would create a second primary).
        try:
            instance_detail = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            instance_list = instance_detail.get('Reservations', [{}])[0].get('Instances', []) if instance_detail.get('Reservations') else []
            cur_state = instance_list[0].get('State', {}).get('Name') if instance_list else "not found"
            if cur_state == "running":
                return True
            return False
        except botocore.exceptions.ClientError as err:
            # A not-found instance is a definitive answer: the primary instance
            # does not exist any more (e.g. the whole ASG was deleted long ago
            # and the terminated instances left the describe window), so the
            # stale record can be cleared. Other client errors (throttling,
            # network) stay undetermined: return None to keep the record, a
            # wrong clear would create a second primary.
            if err.response.get("Error", {}).get("Code") == "InvalidInstanceID.NotFound":
                return False
            return None
        except Exception as err:
            return None

# Primary election rules
    def get_instance_license_type(self, instance):
        # Get the license type of the instance by its AWS marketplace product codes.
        # ProductCodes elements are dicts like {'ProductCodeId': ..., 'ProductCodeType': ...},
        # build a set of the ids only: dicts themselves are not hashable.
        cur_product_code_set = {cur_code.get("ProductCodeId") for cur_code in instance.get("ProductCodes", [])}
        for lic_type, product_code in self.license_product_code_map.items():
            if product_code in cur_product_code_set:
                return lic_type
        return ""

    def instance_matches_election_rules(self, instance):
        # Check whether the instance matches the primary election rules
        # in self.primary_election. All the configured rules must match.
        fgt_vm_id = instance.get("InstanceId")
        allowed_asg_names = self.primary_election.get("allowed_asg_names", None)
        if allowed_asg_names:
            cur_asg_name = ""
            for tag in instance.get("Tags", []):
                if tag.get("Key") == "aws:autoscaling:groupName":
                    cur_asg_name = tag.get("Value", "")
                    break
            # The instance tag carries the full ASG name with the module prefix,
            # the configured names do not, so match by suffix.
            if not cur_asg_name or not any(cur_asg_name == name or cur_asg_name.endswith(name) for name in allowed_asg_names):
                return False
        allowed_license_types = self.primary_election.get("allowed_license_types", None)
        if allowed_license_types:
            cur_license_type = self.get_instance_license_type(instance)
            if not cur_license_type or cur_license_type not in allowed_license_types:
                return False
        return True

    def filter_primary_candidates(self, instance_id_list, running_instance_dict):
        # Sort the primary candidate instance list by the primary election rules
        # in self.primary_election. The rules are a preference, not a hard
        # requirement: instances matching the rules are elected first, but when
        # no instance matches, the remaining running instances are still
        # eligible, so the cluster always has a primary.
        matched_id_list = []
        unmatched_id_list = []
        for cur_vm_id in instance_id_list:
            instance = running_instance_dict.get(cur_vm_id)
            if not instance:
                continue
            if self.instance_matches_election_rules(instance):
                matched_id_list.append(cur_vm_id)
            else:
                unmatched_id_list.append(cur_vm_id)
        # Sort the candidates by the instance launch time first, then by the AZ
        # preference: python sort is stable, so the launch time keeps working as
        # the second sort key inside each AZ preference class.
        order_by = self.primary_election.get("order_by", "oldest")
        matched_id_list.sort(key=lambda cur_vm_id: running_instance_dict[cur_vm_id].get("LaunchTime"), reverse=(order_by == "newest"))
        unmatched_id_list.sort(key=lambda cur_vm_id: running_instance_dict[cur_vm_id].get("LaunchTime"), reverse=(order_by == "newest"))
        # preferred_azs is a soft preference: instances in these AZs are sorted
        # before the others, the others are still eligible when there is no
        # instance in these AZs.
        preferred_azs = self.primary_election.get("preferred_azs", None)
        if preferred_azs:
            matched_id_list.sort(key=lambda cur_vm_id: running_instance_dict[cur_vm_id].get("Placement", {}).get("AvailabilityZone") not in preferred_azs)
            unmatched_id_list.sort(key=lambda cur_vm_id: running_instance_dict[cur_vm_id].get("Placement", {}).get("AvailabilityZone") not in preferred_azs)
        # The matched candidates come first, the unmatched ones are only elected
        # when there is no matched candidate (or no matched candidate could be
        # configured).
        return matched_id_list + unmatched_id_list
    
    def check_primary(self, fgt_vm_id):
        self.logger.info(f"Check and update primary record in Dynamo DB.")
        # Lock primary_instance and asg_instances for the whole primary election,
        # so two concurrent terminates can not elect two primaries. The config upload
        # to FortiGate inside takes time, but the election decision and the primary
        # record update must be atomic, so keep them in the same lock range.
        b_locked_1 = self.lock_dydb("primary_instance")
        b_locked_2 = self.lock_dydb("asg_instances")
        if not b_locked_1 or not b_locked_2:
            self.logger.error("Could not lock primary_instance/asg_instances in Dynamo DB, skip check primary.")
            self.unlock_dydb("primary_instance")
            self.unlock_dydb("asg_instances")
            return
        # FortiGate instance auto-scaling configuration
        primary_instance_id, primary_ip = self.get_primary()
        if primary_instance_id and primary_instance_id != fgt_vm_id:
            # The recorded primary can be stale, e.g. the whole ASG was deleted
            # between deployments: no terminate event ran for it, so the record
            # was never cleared and every new launch joins as a secondary of a
            # dead primary. Re-elect below when the primary is not running.
            b_running = self.is_instance_running(primary_instance_id)
            if b_running is False:
                self.update_primary("", "")
                primary_instance_id = None
                primary_ip = None
        if not primary_instance_id or primary_instance_id == fgt_vm_id:
            fgt_port = ""
            if self.fgt_login_port_number:
                fgt_port = ":" + self.fgt_login_port_number
            # Get next primary instance
            state_name_list = ["running"]
            running_instance_dict = self.get_instance_dict(state_name_list)
            b_succ = False
            fgt_instanceid_list_dict = self.get_asg_instance_list_dydb()
            fgt_instanceid_list = []
            for instance_dict in fgt_instanceid_list_dict:
                fgt_instanceid_list.extend(instance_dict.values())
            # Apply the primary election rules (allowed ASGs, license types,
            # newest first) to filter and sort the candidates.
            fgt_instanceid_list = self.filter_primary_candidates(fgt_instanceid_list, running_instance_dict)
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
                temp_str = ""
                if self.fmg_integration:
                    if self.fmg_integration.get("primary_only", False):
                        temp_str += """
                        config system vdom-exception
                            edit 0
                                set object system.central-management
                            next
                        end
                        """
                    fmg_ip = self.fmg_integration.get("ip", "")
                    fmg_sn = self.fmg_integration.get("sn", "")
                    fmg_vrf_select = self.fmg_integration.get("vrf_select", "")
                    if fmg_ip and fmg_sn:
                        temp_str += f"""
                        config system central-management
                            set type fortimanager
                            set fmg {fmg_ip}
                            set serial-number {fmg_sn}
                        """
                        if fmg_vrf_select:
                            temp_str += f"set vrf-select {fmg_vrf_select}\n"
                        temp_str += "end\n"
                temp_str += f"""
                config system auto-scale
                    set status enable
                    set sync-interface "{self.fgt_primary_port}"
                    set role primary
                    set psksecret "{self.fgt_system_autoscale_psksecret}"
                end
                """
                if self.health_check_port != 0 and self.health_check_protocol == "HTTP":
                    temp_str += f"""
                    config system probe-response
                        set mode http-probe
                        set port "{self.health_check_port}"
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
                if self.primary_scalein_protection:
                    self.set_primary_scalein_protection(fgt_vm_id)
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
        self.unlock_dydb("primary_instance")
        self.unlock_dydb("asg_instances")

# FortiGate configuration
    def gen_config_content(self, fgt_vm_id):
        gwlb_ips = json.loads(os.getenv('gwlb_ips'))
        user_conf = self.get_user_config_from_dydb()
        user_conf_s3 = json.loads(os.getenv('user_conf_s3'))
        fgt_multi_vdom = os.getenv('fgt_multi_vdom') == 'true'
        create_geneve_for_all_az = os.getenv('create_geneve_for_all_az') == 'true'
        az_name_map = json.loads(os.getenv('az_name_map'))
        rst = ""

        # The device indexes existing on this instance. A non-critical
        # interface whose create/attach failed does not block the launch, so
        # the configuration of the missing interface must be skipped too,
        # otherwise the interface commands reference a port which does not
        # exist and the whole configuration upload fails.
        instance_detail = self.ec2_client.describe_instances(InstanceIds=[fgt_vm_id])
        existing_device_indexes = set()
        if instance_detail and instance_detail['Reservations'] and instance_detail['Reservations'][0]['Instances']:
            for intf in instance_detail['Reservations'][0]['Instances'][0]['NetworkInterfaces']:
                existing_device_indexes.add(intf.get("Attachment").get("DeviceIndex"))

        # unset auth-lockout-duration 
        if fgt_multi_vdom:
            rst += "config global\n"
        rst += "config user setting\n"
        rst += "unset auth-lockout-duration\n"
        rst += "end\n"
        if fgt_multi_vdom:
            rst += "end\n"
        # Geneve tunnel
        for intf_name, intf_conf in self.intf_setting.items():
            # Skip the interface which does not exist on this instance (a
            # non-critical interface whose create/attach failed before).
            if intf_conf.get("device_index") not in existing_device_indexes:
                self.logger.warning(f"Skip the configuration of the interface {intf_name}, it does not exist on the instance.")
                continue
            vdom = intf_conf.get("vdom", "root")
            if fgt_multi_vdom:
                rst += f"config vdom\nedit {vdom}\n"
            
            if intf_conf.get("to_gwlb") and gwlb_ips:
                az_list = intf_conf["subnet_id_map"].keys() if create_geneve_for_all_az else [self.fgt_az]
                intf_device_index = intf_conf.get("device_index")
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

        # FortiGate instance auto-scaling configuration
        if self.enable_fgt_system_autoscale:
            # Lock primary_instance for the primary claim: check-then-set must be atomic,
            # otherwise two concurrent launches could both become primary.
            b_locked = self.lock_dydb("primary_instance")
            if not b_locked:
                self.logger.error("Could not lock primary_instance in Dynamo DB.")
                # None marks the generation failed, an empty string would be
                # a valid (empty) configuration.
                return None
            try:
                primary_instance_id, primary_ip = self.get_primary()
                if primary_instance_id and primary_instance_id != fgt_vm_id:
                    # The recorded primary can be stale, e.g. the whole ASG was
                    # deleted between deployments: no terminate event runs then,
                    # so no re-election ever clears the record and every new
                    # launch would join as a secondary of a dead primary. Treat
                    # a primary that is not running any more as empty and claim
                    # a new primary below.
                    b_running = self.is_instance_running(primary_instance_id)
                    if b_running is False:
                        self.update_primary("", "")
                        primary_instance_id = None
                        primary_ip = None
                if not primary_instance_id:
                    # The first claim of an empty primary is also an election, so the
                    # instance must match the primary election rules. Otherwise wait a
                    # while and re-check: a rule-matching instance may launch and claim
                    # the empty primary, then this instance can join as a secondary.
                    instance_detail = self.ec2_client.describe_instances(InstanceIds=[fgt_vm_id])
                    cur_instance = instance_detail['Reservations'][0]['Instances'][0] if instance_detail['Reservations'] and instance_detail['Reservations'][0]['Instances'] else {}
                    if self.instance_matches_election_rules(cur_instance):
                        self.update_primary(fgt_vm_id, self.fgt_primary_ip)
                        primary_instance_id = fgt_vm_id
                        primary_ip = self.fgt_primary_ip
                        if self.primary_scalein_protection:
                            self.set_primary_scalein_protection(fgt_vm_id)
                    else:
                        # Wait a while and re-check whether a primary has appeared.
                        # Release the lock during the wait, otherwise other instances
                        # can not claim the empty primary and the wait never succeeds.
                        self.unlock_dydb("primary_instance")
                        # Wait up to 60 seconds in total, check the primary every 10 seconds.
                        primary_wait_timeout = 60
                        primary_wait_interval = 10
                        waited_time = 0
                        while waited_time < primary_wait_timeout:
                            time.sleep(primary_wait_interval)
                            waited_time += primary_wait_interval
                            primary_instance_id, primary_ip = self.get_primary()
                            if primary_instance_id:
                                break
                        if not primary_instance_id:
                            # Still no primary after the wait: claim the primary as a
                            # fallback, otherwise this instance gets no usable auto-scale
                            # configuration.
                            if not self.lock_dydb("primary_instance"):
                                self.logger.error("Could not lock primary_instance in Dynamo DB.")
                                # None marks the generation failed, an empty
                                # string would be a valid (empty) configuration.
                                return None
                            try:
                                # Re-check under the lock to avoid racing a concurrent claim.
                                primary_instance_id, primary_ip = self.get_primary()
                                if not primary_instance_id:
                                    self.update_primary(fgt_vm_id, self.fgt_primary_ip)
                                    primary_instance_id = fgt_vm_id
                                    primary_ip = self.fgt_primary_ip
                                    if self.primary_scalein_protection:
                                        self.set_primary_scalein_protection(fgt_vm_id)
                            finally:
                                self.unlock_dydb("primary_instance")
            finally:
                self.unlock_dydb("primary_instance")
            autoscale_role = "Primary"
            if primary_instance_id == fgt_vm_id:
                temp_str = ""
                if self.fmg_integration:
                    if self.fmg_integration.get("primary_only", False):
                        temp_str += """
                        config system vdom-exception
                            edit 0
                                set object system.central-management
                            next
                        end
                        """
                    fmg_ip = self.fmg_integration.get("ip", "")
                    fmg_sn = self.fmg_integration.get("sn", "")
                    fmg_vrf_select = self.fmg_integration.get("vrf_select", "")
                    if fmg_ip and fmg_sn:
                        temp_str += f"""
                        config system central-management
                            set type fortimanager
                            set fmg {fmg_ip}
                            set serial-number {fmg_sn}
                        """
                        if fmg_vrf_select:
                            temp_str += f"set vrf-select {fmg_vrf_select}\n"
                        temp_str += "end\n"
                temp_str += f"""
                config system auto-scale
                    set status enable
                    set sync-interface "{self.fgt_primary_port}"
                    set role primary
                    set psksecret "{self.fgt_system_autoscale_psksecret}"
                end
                """
                if self.health_check_port != 0 and self.health_check_protocol == "HTTP":
                    temp_str += f"""
                    config system probe-response
                        set mode http-probe
                        set port "{self.health_check_port}"
                    end
                """
            else:
                autoscale_role = "Secondary"
                temp_str = ""
                if self.fmg_integration and not self.fmg_integration.get("primary_only", False):
                    fmg_ip = self.fmg_integration.get("ip", "")
                    fmg_sn = self.fmg_integration.get("sn", "")
                    fmg_vrf_select = self.fmg_integration.get("vrf_select", "")
                    if fmg_ip and fmg_sn:
                        temp_str += f"""
                        config system central-management
                            set type fortimanager
                            set fmg {fmg_ip}
                            set serial-number {fmg_sn}
                        """
                        if fmg_vrf_select:
                            temp_str += f"set vrf-select {fmg_vrf_select}\n"
                        temp_str += "end\n"
                temp_str += f"""
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
                        
        return rst

    def upload_config(self, config_content, fgt_private_ip):
        self.logger.info("Upload configuration to FortiGate instance.")
        payload = {
            "service" : "fgt_vm",
            "operation" : "upload_config",
            "parameters" : {
                "private_ip" : fgt_private_ip,
                "config_content": config_content
            }
        }
        b_succ, response = self.invoke_lambda(payload, "fgt", "Event")
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
            "service" : "fgt_vm",
            "operation" : "change_password",
            "parameters" : {
                "private_ip" : fgt_private_ip,
                "fgt_vm_id": fgt_vm_id
            }
        }
        b_succ, response = self.invoke_lambda(payload, "fgt")
        return b_succ

    def get_user_config_from_dydb(self):
        self.logger.info("Get user configuration from DynamoDB.")
        rst = ""
        try:
            response = self.get_item_from_dydb("user_config", ["content"])
            if response:
                rst = response.get('content')
                if rst:
                    rst = base64.b64decode(rst).decode('utf-8') 
        except Exception as err:
            self.logger.error(f"Could not get instance list of ASG: {err}")
        return rst

def clean_terminated_vms(logger, intf_object, fgtconf_object):
    logger.info("Clean up terminated vms.")
    # Get terminated or terminating instance ID list
    state_name_list = ["terminated", "shutting-down"]
    terminated_instance_dict = fgtconf_object.get_instance_dict(state_name_list)
    # Get existing ASG created instance ID list
    fgt_instanceid_list_dict = fgtconf_object.get_asg_instance_list_dydb()
    fgt_instanceid_list = []
    for instance_dict in fgt_instanceid_list_dict:
        fgt_instanceid_list.extend(instance_dict.values())
    # Also check the primary instance: it can be missing from the instance list
    # (e.g. its add write was lost), and terminating it is what triggers check_primary
    # to re-elect a primary or clear the stale primary record.
    primary_instance_id, primary_ip = fgtconf_object.get_primary()
    if primary_instance_id and primary_instance_id not in fgt_instanceid_list:
        fgt_instanceid_list.append(primary_instance_id)
    # Check instances that been terminated but not been clean up. This may happens when terminate event not been triggered, like manually terminate the instance.
    clean_id_list = []
    for vm_id in fgt_instanceid_list:
        if vm_id in terminated_instance_dict:
            clean_id_list.append(vm_id)
    # Clean terminated instances
    for vm_id in clean_id_list:
        intf_object.set_vm_id(vm_id)
        intf_object.do_terminate()

        fgtconf_object.set_vm_id(vm_id)
        fgtconf_object.do_terminate()

def complete_lifecycle(logger, event_detail, result="ABANDON"):
    logger.info(f"Complete lifecycle action with result: {result}.")
    asg_client = boto3.client('autoscaling')
    try:
        asg_client.complete_lifecycle_action(
            LifecycleHookName=event_detail.get('LifecycleHookName', ""),
            AutoScalingGroupName=event_detail.get('AutoScalingGroupName', ""),
            LifecycleActionToken=event_detail.get('LifecycleActionToken', ""),
            LifecycleActionResult=result
        )
    except ClientError as e:
        logger.error(f"Error completing life cycle hook for instance: {e.response['Error']['Code']}")

# How tolerant the launch is to failures. ABANDON terminates the instance, the
# ASG replaces it with a new one.
# - strict : any launch failure abandons the instance, the ASG gets only fully
#            working instances, at the cost of possible launch/replace loops
#            when a failure repeats.
# - normal : a failure of a required part abandons the instance. Failures of
#            optional parts (e.g. a public IP association, the DynamoDB track
#            record) and of non-critical additional interfaces only degrade
#            the launch, the instance stays.
# - lenient: no launch failure abandons the instance. Keep it for debugging
#            (a replaced instance loses its failure state) and for the first
#            deployments before the setup is verified.
LAUNCH_TOLERANCE_LEVELS = ["strict", "normal", "lenient"]

def abandon_on_launch_failure(logger, failure_kind, tolerance, event_detail, fgt_vm_id):
    # Decide from the failure kind and the tolerance level whether to abandon
    # the instance. Returns True when the hook was completed and the handler
    # must stop processing.
    abandon = False
    if tolerance == "strict":
        abandon = True
    elif tolerance == "normal":
        # Only the required-part failures ("failed") abandon, the degraded
        # launches (optional-part failures) continue.
        abandon = (failure_kind == "failed")
    # lenient: never abandon.
    if abandon:
        logger.info(f"{failure_kind} launch of instance {fgt_vm_id} is beyond the tolerance {tolerance}, abandon the instance.")
        complete_lifecycle(logger, event_detail, result="ABANDON")
    else:
        logger.warning(f"{failure_kind} launch of instance {fgt_vm_id} within the tolerance {tolerance}, keep the instance.")
    return abandon

def get_launch_tolerance(logger):
    tolerance = os.getenv('lambda_failure_tolerance', 'lenient')
    if tolerance not in LAUNCH_TOLERANCE_LEVELS:
        logger.warning(f"Unknown lambda_failure_tolerance: {tolerance}, fall back to lenient.")
        tolerance = "lenient"
    return tolerance

def lambda_handler(event, context):
    logger = logging.getLogger("fgt_asg_lambda")
    logger.setLevel(logging.INFO)
    # Defaults keep the exception handler below working when the event is malformed
    event_detail = {}
    detail_type = ""
    try:
        event_detail = event["detail"]
        fgt_vm_id = event_detail["EC2InstanceId"]
        detail_type = event["detail-type"]
        hook_name = event_detail.get('LifecycleHookName', '')

        # Early skip: the EventBridge rule routes all the lifecycle events of the
        # ASG to this Lambda, skip the hooks not managed by this Lambda, like
        # the hooks from other automations on the same ASG.
        managed_hooks = ['fgt_asg_launch_hook', 'fgt_asg_terminate_hook']
        if detail_type in ["EC2 Instance-launch Lifecycle Action", "EC2 Instance-terminate Lifecycle Action"]:
            # The hook name may contain a module_prefix, so check the managed
            # hook name as a substring of the hook name.
            if not any(managed_hook in hook_name for managed_hook in managed_hooks):
                logger.info(f"Skip unmanaged lifecycle hook: {hook_name}.")
                return {}

        # Initiate objects
        intf_object = NetworkInterface(logger)
        fgtconf_object = FgtConf(logger)

        # If detail_type is launch related, check and clean the VMs before main operation
        if detail_type in ["EC2 Instance-launch Lifecycle Action", "EC2 Instance Launch Successful"]:
            clean_terminated_vms(logger, intf_object, fgtconf_object)

        ## Network Interface operations
        intf_object.set_vm_id(fgt_vm_id)
        intf_outcome = intf_object.main(detail_type)
        if detail_type == "EC2 Instance-launch Lifecycle Action" and intf_outcome in ["failed", "degraded"]:
            tolerance = get_launch_tolerance(logger)
            if abandon_on_launch_failure(logger, intf_outcome, tolerance, event_detail, fgt_vm_id):
                return {}

        ## FortiGate configuration operations
        fgtconf_object.set_vm_id(fgt_vm_id)
        fgtconf_outcome = fgtconf_object.main(detail_type)
        if detail_type == "EC2 Instance-launch Lifecycle Action" and fgtconf_outcome in ["failed", "degraded"]:
            tolerance = get_launch_tolerance(logger)
            if abandon_on_launch_failure(logger, fgtconf_outcome, tolerance, event_detail, fgt_vm_id):
                return {}

        # If detail_type is terminate related, check and clean the VMs after main operation
        if detail_type in ["EC2 Instance-terminate Lifecycle Action", "EC2 Instance Terminate Successful"]:
            clean_terminated_vms(logger, intf_object, fgtconf_object)

        # Complete the managed lifecycle hook after all the operations succeeded
        if detail_type in ["EC2 Instance-launch Lifecycle Action", "EC2 Instance-terminate Lifecycle Action"]:
            complete_lifecycle(logger, event_detail, result="CONTINUE")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error in fgt_asg_lambda: {e}")
        # Only the lifecycle action events have a hook to complete. An
        # unexpected error abandons the hook so the ASG does not wait for its
        # timeout, except under lenient tolerance which keeps the instance
        # alive for debugging and lets the hook continue.
        if detail_type in ["EC2 Instance-launch Lifecycle Action", "EC2 Instance-terminate Lifecycle Action"]:
            if detail_type == "EC2 Instance-terminate Lifecycle Action":
                # On termination ABANDON does not cancel the termination, it
                # only stops the remaining hooks, so complete with CONTINUE
                # to let the other hooks run.
                complete_lifecycle(logger, event_detail, result="CONTINUE")
            else:
                tolerance = get_launch_tolerance(logger)
                if tolerance != "lenient":
                    complete_lifecycle(logger, event_detail, result="ABANDON")
                else:
                    complete_lifecycle(logger, event_detail, result="CONTINUE")
        return {}


