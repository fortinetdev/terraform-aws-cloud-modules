## EC2 instance
variable "ami_id" {
  description = "The AMI ID of FortiOS image. If you leave this blank, Terraform will get the AMI ID from AWS market place with the given FortiOS version."
  type        = string
  default     = ""
}

variable "instance_name" {
  description = "FortiGate instance name."
  type        = string
  default     = ""
}

variable "keypair_name" {
  description = "The keypair name that used in FortiGate EC2 instance."
  type        = string
}

variable "availability_zone" {
  description = " AZ to start the instance in."
  type        = string
  default     = ""
}

variable "instance_type" {
  description = "Provide the instance type for the FortiGate instances."
  default     = "c5.xlarge"
  type        = string
}

variable "license_type" {
  description = "Provide the license type for the FortiGate instances. Options: on_demand, byol. Default is on_demand."
  default     = "on_demand"
  type        = string
}

variable "fgt_version" {
  description = "Provide the FortiGate version for the FortiGate instances. If the whole version been provided, please make sure the version is exist. If part of version been provided, such as 7.2, will using the latest release of this version. Default is 7.2."
  default     = "7.2"
  type        = string
}

variable "fgt_hostname" {
  description = "FortiGate instance hostname."
  default     = ""
  type        = string
}

variable "fgt_password" {
  description = "FortiGate instance login password. If not set, the default password will be the instance ID. You need to change it at the first time login by GUI or CLI."
  default     = ""
  type        = string
}

variable "fgt_admin_https_port" {
  description = "FortiGate instance HTTPS admin access port."
  default     = ""
  type        = string
}

variable "fgt_admin_ssh_port" {
  description = "FortiGate instance SSH admin access port."
  default     = ""
  type        = string
}

variable "fgt_multi_vdom" {
  description = "Whether FortiGate instance enable multi-vdom mode. Default is false. Note: Only license_type set to byol could enable multi-vdom mode."
  default     = false
  type        = bool
}

variable "user_conf" {
  description = "User configuration in CLI format that will applied to the FortiGate instance."
  default     = ""
  type        = string
}

variable "lic_file_path" {
  description = "FortiGate license file path that used for BYOL type of FortiGate instance."
  default     = ""
  type        = string
}

variable "fortiflex_sn" {
  description = "FortiFlex serial number that used for BYOL type of FortiGate instance."
  default     = ""
  type        = string
}

variable "cpu_options" {
  description = "CPU options apply to the instance at launch time."
  default     = {}
  type = object({
    amd_sev_snp      = optional(string, "")
    core_count       = optional(string, "")
    threads_per_core = optional(string, "")
  })
}

## Network interfaces
variable "network_interfaces" {
  description = <<-EOF
  Network interfaces configuration for FortiGate VM instance.
  Format:
  ```
    network_interfaces = {
        \<Key\> = {
            \<Option\> = \<Option value\>
        }
    }
  ```
  Key:
    Name of the interface.
    
  Options:
    - device_index       : (Required|int) Integer to define the network interface index. Interface with `0` will be attached at boot time.
    - subnet_id          : (Required|string) Subnet ID to create the ENI in.
    - vdom               : (Optional|string) Vdom name that the interface belongs to. Only works when vdom mode is multi-vdom. Default will be root if not set and vdom mode is multi-vdom.
    - description        : (Optional|string) Description for the network interface.
    - private_ips        : (Optional|list) List of private IPs to assign to the ENI without regard to order.
    - source_dest_check  : (Optional|bool) Whether to enable source destination checking for the ENI. Defaults false.
    - security_groups    : (Optional|list) List of security group IDs to assign to the ENI. Defaults null.
    - enable_public_ip   : (Optional|bool) Whether to assign a public IP for the ENI. Defaults to false.
    - public_ipv4_pool   : (Optional|string) Specify EC2 IPv4 address pool. If not set, Amazon's poll will be used. Only useful when `enable_public_ip` is set to true.
    - existing_eip_id    : (Optional|string) Associate an existing EIP to the ENI. Sould set enable_public_ip to false.
  
  Example:
  ```
  network_interfaces = {
    mgmt = {
      device_index       = 0
      subnet_id          = \<SUBNET_ID\>
      enable_public_ip   = true
      source_dest_check  = true
      security_groups = ["\<SECURITY_GROUP_ID\>"]
    },
    public1 = {
      device_index     = 1
      subnet_id        = \<SUBNET_ID\>
      existing_eip_id  = \<ELISTIC_IP_ID\>
    }
  }
  ```
  EOF

  type = any
  validation {
    condition = var.network_interfaces == null ? true : alltrue([
      for k, v in var.network_interfaces :
      alltrue([
        for sk, sv in v : contains([
          "device_index",
          "subnet_id",
          "vdom",
          "description",
          "private_ips",
          "source_dest_check",
          "security_groups",
          "enable_public_ip",
          "public_ipv4_pool",
        "existing_eip_id"], sk)
      ])
    ])
    error_message = "One or more argument(s) can not be identified, available options: device_index, subnet_id, vdom, description, private_ips, source_dest_check, security_groups, enable_public_ip, public_ipv4_pool, existing_eip_id."
  }
}

## FGT config

## Tag related
variable "tags" {
  description = <<-EOF
  Tags that applies to related resources.
  Format:
  ```
    tags = {
        \<Option\> = \<Option value\>
    }
  ```
  Options:
    - general          :  Tags will add to all resources.
    - instance         :  Tags for EC2 instance.
    - interface        :  Tags for network interfaces.
    - eip              :  Tags for Elistic IPs.
    - eip_association  :  Tags for Elistic IP Associations.
    
  Example:
  ```
  tags = {
    general = {
      Created_from = "Terraform"
    },
    instance = {
      Used_to = "ASG"
    }
  }
  ```
  EOF

  default = {}
  type    = map(map(string))
  validation {
    condition = var.tags == null ? true : alltrue([
      for k, v in var.tags : contains([
        "general",
        "instance",
        "interface",
        "eip",
        "eip_association"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: general, instance, interface, eip, eip_association."
  }
}

variable "module_prefix" {
  description = "Prefix that will be used in the whole module."
  type        = string
  default     = ""
}