provider "aws" {
  access_key = var.access_key
  secret_key = var.secret_key
  region     = var.region
}

locals {
  module_prefix = var.module_prefix == "" ? "" : "${var.module_prefix}-"
  # Subnets
  subnets = var.existing_subnets == null ? module.security-vpc.subnets : {
    for k, v in var.existing_subnets : "${local.module_prefix}${k}" => v
  }
}

# Create security VPC including subnets, IGW, and security groups
module "security-vpc" {
  source = "../../modules/aws/vpc"

  existing_vpc             = var.existing_security_vpc
  existing_igw             = var.existing_igw
  existing_security_groups = var.existing_security_groups
  vpc_name                 = var.vpc_name
  igw_name                 = var.igw_name
  security_groups          = var.security_groups
  vpc_cidr_block           = var.vpc_cidr_block
  subnets                  = var.subnets
  module_prefix            = local.module_prefix

  tags = {
    general = var.general_tags
  }
}

# Create VPC route tables
module "security_route_table" {
  source = "../../modules/aws/vpc_route_table"

  for_each = var.route_tables
  vpc_id   = module.security-vpc.vpc_id
  rt_name  = each.key
  rt_association_subnets = [
    for v in each.value.rt_association_subnets : (
      v.id != null ? v.id : local.subnets["${local.module_prefix}${v.name}"].id
    ) if v.id != null || (v.name != null && lookup(local.subnets, "${local.module_prefix}${v.name}", false) != false)
  ]
  rt_association_gateways = [
    for v in each.value.rt_association_gateways : (
      v.id != null ? v.id : module.security-vpc.igw_id
    ) if v.id != null || (v.name != null && v.name == var.igw_name)
  ]
  routes = {
    for k, v in each.value.routes : k => merge([
      for sk, sv in v : [
        (
          sk == "gateway" && sv != null ? {
            gateway_id = (
              sv.id != null ? sv.id : sv.name == var.igw_name ? module.security-vpc.igw_id : null
            )
          } : {}
        ),
        (
          sk == "nat_gateway" && sv != null ? {
            nat_gateway_id = sv.id
          } : {}
        ),
        (
          sk == "network_interface" && sv != null ? {
            network_interface_id = (
              sv.id != null ? sv.id : module.fgts[split(".", sv.name)[0]].fgt_interface_ids["${local.module_prefix}${split(".", sv.name)[1]}"]
            )
          } : {}
        ),
        (
          sv != null ? {
            "${sk}" = sv
          } : {}
        )
      ][sk == "gateway" ? 0 : sk == "nat_gateway" ? 1 : sk == "network_interface" ? 2 : 3]
    ]...)
  }
  depends_on = [
    module.security-vpc,
    module.fgts
  ]
}

# Create FortiGate Auto Scaling group
locals {
  secgrp_idmap_with_prefixname = {
    for k, v in module.security-vpc.security_group : v.prefix_name => v.id
  }
}
module "fgts" {
  source   = "../../modules/fortigate/fgt"
  for_each = var.fgts

  module_prefix = local.module_prefix
  # FortiGate instance template
  instance_name        = each.key
  ami_id               = each.value.ami_id
  fgt_version          = each.value.fgt_version
  instance_type        = each.value.instance_type
  license_type         = each.value.license_type
  fgt_hostname         = each.value.fgt_hostname
  fgt_password         = each.value.fgt_password
  fgt_multi_vdom       = each.value.fgt_multi_vdom
  lic_file_path        = each.value.lic_file_path
  fortiflex_sn         = each.value.fortiflex_sn
  keypair_name         = each.value.keypair_name
  fgt_admin_https_port = each.value.fgt_admin_https_port
  fgt_admin_ssh_port   = each.value.fgt_admin_ssh_port
  user_conf = (
    lookup(each.value, "user_conf_content", "") != "" && lookup(each.value, "user_conf_file_path", "") != "" ?
    format("%s\n%s", file(each.value["user_conf_file_path"]), each.value["user_conf_content"]) :
    lookup(each.value, "user_conf_file_path", "") != "" ? file(each.value["user_conf_file_path"]) : lookup(each.value, "user_conf_content", "")
  )

  network_interfaces = {
    for k, v in each.value.network_interfaces : k => merge([
      for sk, sv in v : [
        (
          sk == "subnet" && sv != null ? {
            subnet_id = (
              sv.id != null ? sv.id : sv.name != null && lookup(local.subnets, "${local.module_prefix}${sv.name}", null) != null ? local.subnets["${local.module_prefix}${sv.name}"].id : null
            )
          } : {}
        ),
        (
          sk == "security_groups" && sv != null ? {
            security_groups = [
              for sg in sv : (
                sg.id != null ? sg.id : sg.name != null && lookup(local.secgrp_idmap_with_prefixname, "${local.module_prefix}${sg.name}", null) != null ? local.secgrp_idmap_with_prefixname["${local.module_prefix}${sg.name}"] : null
              )
            ]
          } : {}
        ),
        (
          sv == null ? {} : {
            "${sk}" = sv
          }
        )
      ][sk == "subnet" ? 0 : sk == "security_groups" ? 1 : 2]
    ]...)
  }

  tags = {
    general = var.general_tags
  }
  depends_on = [
    module.security-vpc,
  ]
}
