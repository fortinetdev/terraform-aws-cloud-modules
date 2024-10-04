provider "aws" {
  access_key = var.access_key
  secret_key = var.secret_key
  region     = var.region
}

locals {
  module_prefix        = var.module_prefix == "" ? "" : "${var.module_prefix}-"
  internal_port_prefix = var.fgt_intf_mode == "1-arm" ? "${local.module_prefix}fgt_login_" : "${local.module_prefix}fgt_internal_"
  # Security VPC subnets
  subnet_cidr_block = var.subnet_cidr_block == "" ? var.vpc_cidr_block : var.subnet_cidr_block
  cidr_split        = split("/", local.subnet_cidr_block)
  base_ip           = split(".", element(local.cidr_split, 0))
  base_netmask      = element(local.cidr_split, 1) == "" ? 99 : tonumber(element(local.cidr_split, 1))
  step_num          = local.base_netmask <= 19 ? 1 : 16
  subnet_netmask    = local.step_num == 1 ? 24 : 28
  subnet_prefixs    = var.fgt_intf_mode == "1-arm" ? ["fgt_login_", ""] : ["fgt_login_", "fgt_internal_"]
  create_subnets = var.existing_subnets != null ? {} : (var.subnets != null && var.subnets != {}) ? var.subnets : local.base_netmask > 24 ? {} : merge(
    merge([
      for az_i in range(length(var.availability_zones)) : merge([
        for sn_i in range(length(local.subnet_prefixs)) : {
          "${local.subnet_prefixs[sn_i]}${var.availability_zones[az_i]}" = {
            cidr_block = join(".",
              [
                "${local.base_ip[0]}",
                "${local.base_ip[1]}",
                "%{if local.step_num == 1}${tostring(tonumber(local.base_ip[2]) + az_i * length(local.subnet_prefixs) + sn_i)}%{else}${local.base_ip[2]}%{endif}",
                "%{if local.step_num != 1}${tostring(tonumber(local.base_ip[3]) + (az_i * length(local.subnet_prefixs) + sn_i) * 16)}%{else}${local.base_ip[2]}%{endif}/${local.subnet_netmask}"
              ]
            )
            availability_zone = "${var.availability_zones[az_i]}"
          }
        } if local.subnet_prefixs[sn_i] != ""
      ]...)
    ]...),
    var.enable_privatelink_dydb ? {
      "privatelink_ep" = {
        cidr_block = join(".",
          [
            "${local.base_ip[0]}",
            "${local.base_ip[1]}",
            "%{if local.step_num == 1}${tostring(tonumber(local.base_ip[2]) + (length(var.availability_zones) - 1) * length(local.subnet_prefixs) + length(local.subnet_prefixs))}%{else}${local.base_ip[2]}%{endif}",
            "%{if local.step_num != 1}${tostring(tonumber(local.base_ip[3]) + ((length(var.availability_zones) - 1) * length(local.subnet_prefixs) + length(local.subnet_prefixs)) * 16)}%{else}${local.base_ip[2]}%{endif}/${local.subnet_netmask}"
          ]
        )
        availability_zone = "${var.availability_zones[1]}"
      }
    } : {}
  )

  # Subnets
  subnets = var.existing_subnets == null ? module.security-vpc.subnets : {
    for k, v in var.existing_subnets : "${local.module_prefix}${k}" => v
  }

  # Security VPC route table
  route_tables = {
    "secvpc" = (module.security-vpc.has_igw == false ||
      length([for k, v in local.create_subnets : k if startswith(k, "fgt_login_")]) == 0) ? {} : {
      fgt_login = {
        routes = {
          local_pc = {
            destination_cidr_block = "0.0.0.0/0"
            gateway_id             = module.security-vpc.igw_id
          }
        },
        rt_association_subnets = [for k, v in local.create_subnets : local.subnets["${local.module_prefix}${k}"]["id"] if startswith(k, "fgt_login_")]
      }
    }
  }
  # Spoke VPC Gateway Load Balancer Endpoints
  gwlb_endps = merge([
    for vpc_name, vpc_value in var.spk_vpc : {
      for subnet_id in vpc_value.gwlbe_subnet_ids : "gwlbe-${subnet_id}" => {
        vpc_id    = "${vpc_value.vpc_id}"
        subnet_id = "${subnet_id}"
      }
    }
  ]...)
  # AZ name map
  az_name_map = {
    for az_i in range(length(var.availability_zones)) : var.availability_zones[az_i] => "geneve-az${az_i + 1}"
  }
}


resource "null_resource" "validation_check_subnet_cidr" {
  count = var.existing_subnets == null && var.subnets == null && local.subnet_cidr_block != "" && local.base_netmask > 24 ? (
    <<EOT
    "Auto set subnet do not support netmask larger then 24. Please provide a CIDR block with netmask smaler or equal to 24. Otherwise, please delete this validation and provide the variable \"subnets\" manually.
    The format should be follow the name prefix of \"fgt_login_\", \"fgt_internal_\", \"privatelink_\". Specify the target subnet you needed." 
  EOT
  ) : 0
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
  subnets                  = local.create_subnets
  module_prefix            = local.module_prefix

  tags = {
    general = merge(
      var.general_tags,
      {
        created_from = "Terraform"
      }
    ),
    vpc = {
      test_tag = "tgw-test-tag"
    }
  }
}

# Create VPC route tables
module "security_route_table" {
  source = "../../modules/aws/vpc_route_table"

  for_each                = lookup(local.route_tables, "secvpc", {})
  vpc_id                  = module.security-vpc.vpc_id
  rt_name                 = each.key
  routes                  = lookup(each.value, "routes", {})
  rt_association_subnets  = lookup(each.value, "rt_association_subnets", [])
  rt_association_gateways = lookup(each.value, "rt_association_gateways", [])
  depends_on = [
    module.security-vpc
  ]
}

# Create FortiGate Auto Scaling group
locals {
  secgrp_idmap_with_prefixname = {
    for k, v in module.security-vpc.security_group : v.prefix_name => v.id
  }
}
module "fgt_asg" {
  source   = "../../modules/fortigate/fgt_asg"
  for_each = var.asgs
  # FortiGate instance template
  template_name                  = lookup(each.value, "template_name", "")
  ami_id                         = lookup(each.value, "ami_id", "")
  fgt_version                    = lookup(each.value, "fgt_version", "")
  instance_type                  = lookup(each.value, "instance_type", "c5n.xlarge")
  license_type                   = lookup(each.value, "license_type", "on_demand")
  fgt_hostname                   = lookup(each.value, "fgt_hostname", "")
  fgt_password                   = each.value.fgt_password
  fgt_multi_vdom                 = lookup(each.value, "fgt_multi_vdom", false)
  lic_folder_path                = lookup(each.value, "lic_folder_path", null)
  lic_s3_name                    = lookup(each.value, "lic_s3_name", null)
  fortiflex_refresh_token        = lookup(each.value, "fortiflex_refresh_token", "")
  fortiflex_username             = lookup(each.value, "fortiflex_username", "")
  fortiflex_password             = lookup(each.value, "fortiflex_password", "")
  fortiflex_sn_list              = lookup(each.value, "fortiflex_sn_list", [])
  fortiflex_configid_list        = lookup(each.value, "fortiflex_configid_list", [])
  keypire_name                   = each.value.keypair_name
  enable_fgt_system_autoscale    = lookup(each.value, "enable_fgt_system_autoscale", false)
  fgt_system_autoscale_psksecret = lookup(each.value, "fgt_system_autoscale_psksecret", "")
  fgt_login_port_number          = lookup(each.value, "fgt_login_port_number", "")
  user_conf = (
    lookup(each.value, "user_conf_content", "") != "" && lookup(each.value, "user_conf_file_path", "") != "" ?
    format("%s\n%s", file(each.value["user_conf_file_path"]), each.value["user_conf_content"]) :
    lookup(each.value, "user_conf_file_path", "") != "" ? file(each.value["user_conf_file_path"]) : lookup(each.value, "user_conf_content", "")
  )
  user_conf_s3 = lookup(each.value, "user_conf_s3", {})

  # Auto Scale Group
  availability_zones    = var.availability_zones
  asg_name              = each.key
  asg_max_size          = each.value.asg_max_size
  asg_min_size          = each.value.asg_min_size
  asg_desired_capacity  = lookup(each.value, "asg_desired_capacity", null)
  scale_policies        = lookup(each.value, "scale_policies", {})
  create_dynamodb_table = lookup(each.value, "create_dynamodb_table", null)
  dynamodb_table_name   = lookup(each.value, "dynamodb_table_name", null)
  dynamodb_privatelink = var.enable_privatelink_dydb ? {
    vpc_id                      = module.security-vpc.vpc_id
    region                      = var.region
    privatelink_subnet_ids      = [for k, v in local.subnets : v["id"] if startswith(k, "${local.module_prefix}privatelink_")]
    privatelink_security_groups = [for sg_name in each.value.privatelink_security_groups : local.secgrp_idmap_with_prefixname["${local.module_prefix}${sg_name}"]]
  } : null
  network_interfaces = jsondecode(
    var.fgt_intf_mode == "1-arm" ? jsonencode({
      mgmt = {
        device_index      = 0
        subnet_id_map     = { for k, v in local.subnets : v["availability_zone"] => v["id"] if startswith(k, "${local.module_prefix}fgt_login_") }
        enable_public_ip  = true
        to_gwlb           = true
        source_dest_check = true
        security_groups   = [local.secgrp_idmap_with_prefixname["${local.module_prefix}${each.value.intf_security_group["login_port"]}"]]
      }
      }) : jsonencode({
      mgmt = {
        device_index      = 1
        subnet_id_map     = { for k, v in local.subnets : v["availability_zone"] => v["id"] if startswith(k, "${local.module_prefix}fgt_login_") }
        enable_public_ip  = true
        source_dest_check = true
        security_groups   = [local.secgrp_idmap_with_prefixname["${local.module_prefix}${each.value.intf_security_group["login_port"]}"]]
      },
      internal_traffic = {
        device_index    = 0
        to_gwlb         = true
        subnet_id_map   = { for k, v in local.subnets : v["availability_zone"] => v["id"] if startswith(k, "${local.module_prefix}fgt_internal_") }
        security_groups = [local.secgrp_idmap_with_prefixname["${local.module_prefix}${each.value.intf_security_group["internal_port"]}"]]
      }
    })
  )

  create_geneve_for_all_az = var.enable_cross_zone_load_balancing
  gwlb_ips                 = module.security-vpc-gwlb.gwlb_ips
  asg_health_check_type    = "ELB"
  asg_gwlb_tgp             = module.security-vpc-gwlb.gwlb_tgp == null ? null : [module.security-vpc-gwlb.gwlb_tgp.arn]
  lambda_timeout           = 500
  az_name_map              = local.az_name_map
  module_prefix            = local.module_prefix
  tags = {
    general = merge(
      var.general_tags,
      {
        created_from = "Terraform"
      }
    ),
    instance = {
      test_tag = "tgw-test-tag"
    }
  }
  depends_on = [
    module.security-vpc,
    module.security-vpc-gwlb
  ]
}

# Create Cloudwatch Alarm 
resource "aws_cloudwatch_metric_alarm" "hybrid_asg" {
  for_each = var.cloudwatch_alarms

  alarm_name          = "${local.module_prefix}${each.key}"
  comparison_operator = lookup(each.value, "comparison_operator", null)
  evaluation_periods  = lookup(each.value, "evaluation_periods", null)
  metric_name         = lookup(each.value, "metric_name", null)
  namespace           = lookup(each.value, "namespace", null)
  period              = lookup(each.value, "period", null)
  statistic           = lookup(each.value, "statistic", null)
  threshold           = lookup(each.value, "threshold", null)
  dimensions = lookup(each.value, "dimensions", null) == null ? null : {
    for k, v in each.value["dimensions"] : k => "${k == "AutoScalingGroupName" ? "${local.module_prefix}${v}" : v}"
  }
  alarm_description   = lookup(each.value, "alarm_description", null)
  datapoints_to_alarm = lookup(each.value, "datapoints_to_alarm", null)
  alarm_actions = (
    lookup(each.value, "alarm_asg_policies", null) == null ?
    null :
    compact(
      distinct(
        concat(
          lookup(each.value.alarm_asg_policies, "policy_arn_list", []),
          lookup(each.value.alarm_asg_policies, "policy_name_map", null) == null ?
          [] :
          flatten(
            [
              for asg_name, policy_list in each.value.alarm_asg_policies["policy_name_map"] : [
                for policy_name in each.value.alarm_asg_policies["policy_name_map"][asg_name] : module.fgt_asg[asg_name].asg_policy_list[policy_name].arn if lookup(module.fgt_asg[asg_name].asg_policy_list, policy_name, null) != null
              ]
            ]
          )
        )
      )
    )
  )
}

# Create Gateway Load Balancer including GWLB Endpoints
module "security-vpc-gwlb" {
  source = "../../modules/aws/gwlb"

  existing_gwlb                    = var.existing_gwlb
  existing_gwlb_tgp                = var.existing_gwlb_tgp
  existing_gwlb_ep_service         = var.existing_gwlb_ep_service
  gwlb_name                        = var.gwlb_name
  subnets                          = [for k, v in local.subnets : v["id"] if startswith(k, local.internal_port_prefix)]
  tgp_name                         = var.tgp_name
  deregistration_delay             = 30
  enable_cross_zone_load_balancing = var.enable_cross_zone_load_balancing
  health_check = {
    port     = 80
    protocol = "TCP"
  }
  vpc_id               = module.security-vpc.vpc_id
  gwlb_ln_name         = "gwlb-ln"
  gwlb_ep_service_name = var.gwlb_ep_service_name
  gwlb_endps           = local.gwlb_endps
  module_prefix        = local.module_prefix
  depends_on = [
    module.security-vpc
  ]
}

# Create VPC route tables under Spoke VPC
locals {
  spkvpc_rt = merge([
    for vpc_name, vpc_content in var.spk_vpc : merge([
      for rt_name, rt_content in vpc_content.route_tables : {
        "${vpc_name}_${rt_name}" = merge(
          rt_content,
          {
            rt_name = rt_name
            vpc_id  = vpc_content.vpc_id
          }
        )
      }
    ]...) if lookup(vpc_content, "route_tables", false) != false
  ]...)
}

module "spkvpc-rt" {
  source = "../../modules/aws/vpc_route_table"

  for_each    = local.spkvpc_rt
  vpc_id      = each.value["vpc_id"]
  rt_name     = each.value["rt_name"]
  existing_rt = lookup(each.value, "existing_rt", null)
  routes = lookup(each.value, "routes", false) == false ? null : {
    for r_name, r_content in each.value.routes : r_name => merge(
      { for k, v in r_content : k => v if k != "gwlbe_subnet_id" },
      lookup(r_content, "gwlbe_subnet_id", null) == null ? {} : {
        vpc_endpoint_id = [for ep_name, ep_id in module.security-vpc-gwlb.gwlb_endps : ep_id if endswith(ep_name, r_content.gwlbe_subnet_id)][0]
      }
    )
  }
  rt_association_subnets  = lookup(each.value, "rt_association_subnets", [])
  rt_association_gateways = lookup(each.value, "rt_association_gateways", [])
}