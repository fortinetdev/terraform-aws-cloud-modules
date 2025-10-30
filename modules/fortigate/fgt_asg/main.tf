locals {
  chip_type         = strcontains(split(".", var.instance_type)[0], "g") ? "ARM" : "Intel"
  product_code      = var.license_type == "byol" ? (local.chip_type == "ARM" ? "33ndn84xbrajb9vmu5lxnfpjq" : "dlaioq277sglm5mw1y1dmeuqa") : (local.chip_type == "ARM" ? "8gc40z1w65qjt61p9ps88057n" : "2wqkpek696qhdeo7lbbjncqli")
  ami_search_string = var.license_type == "byol" ? "FortiGate-VM*(${var.fgt_version}*" : "FortiGate-VM*(${var.fgt_version}*"
  fos_ami_id        = var.ami_id != "" ? var.ami_id : data.aws_ami.fgt_ami.id
  asg_name          = "${var.module_prefix}${var.asg_name}"
}

data "aws_ami" "fgt_ami" {
  most_recent = true
  owners      = ["aws-marketplace"]

  filter {
    name   = "name"
    values = [local.ami_search_string]
  }

  filter {
    name   = "product-code"
    values = [local.product_code]
  }
}

locals {
  vars = {
    fgt_hostname          = var.fgt_hostname
    fgt_password          = var.fgt_password
    fgt_multi_vdom        = var.fgt_multi_vdom
    network_interfaces    = var.network_interfaces
    fgt_login_port_number = var.fgt_login_port_number
    fmg_integration       = var.fmg_integration
    license_type          = var.license_type
    fgt_primary_port      = "port${[for e in var.network_interfaces : e.device_index + 1 if lookup(e, "mgmt_intf", false)][0]}"
  }
  fgt_userdata = templatefile("${path.module}/fgt-userdata.tftpl", local.vars)
}


## FortiGate instance launch template
resource "aws_launch_template" "fgt" {
  name                   = var.template_name == "" ? null : "${var.module_prefix}${var.template_name}"
  image_id               = local.fos_ami_id
  instance_type          = var.instance_type
  key_name               = var.keypair_name
  update_default_version = true
  user_data              = base64encode(local.fgt_userdata)

  dynamic "network_interfaces" {
    for_each = { for k, v in var.network_interfaces : k => v if v.device_index == 0 }

    content {
      device_index                = 0
      description                 = lookup(network_interfaces.value, "description", null)
      security_groups             = lookup(network_interfaces.value, "security_groups", null)
      subnet_id                   = values(network_interfaces.value["subnet_id_map"])[0]
      associate_public_ip_address = lookup(network_interfaces.value, "enable_public_ip", null)
    }
  }
  dynamic "metadata_options" {
    for_each = var.metadata_options == null ? {} : { "metadata_options" : var.metadata_options }

    content {
      http_endpoint               = metadata_options.value.http_endpoint
      http_tokens                 = metadata_options.value.http_tokens
      http_put_response_hop_limit = metadata_options.value.http_put_response_hop_limit
      http_protocol_ipv6          = metadata_options.value.http_protocol_ipv6
      instance_metadata_tags      = metadata_options.value.instance_metadata_tags
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags = merge(
      lookup(var.tags, "general", {}),
      lookup(var.tags, "instance", {})
    )
  }
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "template", {})
  )
}

## Auto Scaling Group
resource "aws_autoscaling_group" "fgt-asg" {
  name                      = local.asg_name
  max_size                  = var.asg_max_size
  min_size                  = var.asg_min_size
  health_check_grace_period = var.asg_health_check_grace_period
  health_check_type         = var.asg_health_check_type
  desired_capacity          = var.asg_desired_capacity
  target_group_arns         = var.asg_gwlb_tgp
  vpc_zone_identifier       = distinct(values(merge([for k, v in var.network_interfaces : v.subnet_id_map if v.device_index == 0]...)))

  launch_template {
    id      = aws_launch_template.fgt.id
    version = aws_launch_template.fgt.latest_version
  }

  initial_lifecycle_hook {
    name                 = "${var.module_prefix}fgt_asg_launch_hook"
    default_result       = "CONTINUE"
    heartbeat_timeout    = 60
    lifecycle_transition = "autoscaling:EC2_INSTANCE_LAUNCHING"
  }

  initial_lifecycle_hook {
    name                 = "${var.module_prefix}fgt_asg_terminate_hook"
    default_result       = "CONTINUE"
    heartbeat_timeout    = 60
    lifecycle_transition = "autoscaling:EC2_INSTANCE_TERMINATING"
  }

  dynamic "tag" {
    for_each = merge(
      lookup(var.tags, "general", {}),
      lookup(var.tags, "asg", {})
    )

    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  depends_on = [
    aws_cloudwatch_event_target.fgt_asg_launch,
    aws_cloudwatch_event_target.fgt_asg_terminate,
    aws_iam_role_policy.iam_policy,
    aws_lambda_permission.lambda_permission,
    aws_s3_object.fgt_lic,
    aws_s3_object.fgt_lic_track_file,
    aws_s3_object.fgt_intf_track_file,
    aws_dynamodb_table.track_table,
    aws_lambda_function.fgt_asg_lambda_internal
  ]
}

resource "aws_autoscaling_policy" "scale_policy" {
  for_each = var.scale_policies

  autoscaling_group_name    = aws_autoscaling_group.fgt-asg.name
  name                      = each.key
  policy_type               = each.value["policy_type"]
  estimated_instance_warmup = lookup(each.value, "estimated_instance_warmup", null)
  cooldown                  = lookup(each.value, "cooldown", null)
  scaling_adjustment        = lookup(each.value, "scaling_adjustment", null)
  adjustment_type           = lookup(each.value, "adjustment_type", null)
  dynamic "target_tracking_configuration" {
    for_each = { for k, v in each.value : k => v if k == "target_tracking_configuration" }
    content {
      target_value = target_tracking_configuration.value["target_value"]
      dynamic "predefined_metric_specification" {
        for_each = { for k, v in target_tracking_configuration.value : k => v if k == "predefined_metric_specification" }
        content {
          predefined_metric_type = predefined_metric_specification.value["predefined_metric_type"]
          resource_label         = lookup(predefined_metric_specification.value, "resource_label", null)
        }
      }
    }
  }
}

## Lambda
data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "iam_for_lambda" {
  name_prefix        = "${var.module_prefix}lambda_terraform_module_fgt"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "iam", {})
  )
  lifecycle {
    ignore_changes = [
      name,
    ]
  }
}

resource "aws_iam_role_policy" "iam_policy" {
  name_prefix = "${var.module_prefix}lambda_terraform_module_fgt"
  role        = aws_iam_role.iam_for_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Effect   = "Allow",
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Action = [
          "ec2:AllocateAddress",
          "ec2:AssociateAddress",
          "ec2:AttachNetworkInterface",
          "ec2:CreateNetworkInterface",
          "ec2:DescribeAddresses",
          "ec2:DescribeInstances",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeSubnets",
          "ec2:DeleteNetworkInterface",
          "ec2:DetachNetworkInterface",
          "ec2:DisassociateAddress",
          "ec2:ModifyNetworkInterfaceAttribute",
          "ec2:ModifyInstanceAttribute",
          "ec2:ReleaseAddress",
          "ec2:CreateTags",
          "autoscaling:CompleteLifecycleAction",
          "autoscaling:DescribeAutoScalingGroups",
          "autoscaling:SetInstanceProtection",
          "s3:*",
          "s3-object-lambda:*",
          "lambda:InvokeFunction",
          "dynamodb:*"
        ],
        Effect   = "Allow",
        Resource = "*"
      },
      {
        Action = [
          "events:PutRule"
        ],
        Effect   = "Allow",
        Resource = "arn:aws:events:*:*:rule/*"
      }
    ]
  })
}

data "archive_file" "lambda_public" {
  type        = "zip"
  source_file = "${path.module}/fgt-asg-lambda.py"
  output_path = "${path.module}/fgt-asg-lambda.zip"
}

data "archive_file" "lambda_private" {
  type        = "zip"
  source_file = "${path.module}/fgt-asg-lambda-internal.py"
  output_path = "${path.module}/fgt-asg-lambda-internal.zip"
}

locals {
  lic_folder              = var.lic_folder_path == null ? "" : trimsuffix(var.lic_folder_path, "/")
  lic_file_set            = var.lic_s3_name != null ? toset([]) : var.lic_folder_path == null ? toset([]) : fileset(var.lic_folder_path, "*")
  lic_s3_name             = var.lic_s3_name != null ? var.lic_s3_name : aws_s3_bucket.fgt_lic[0].id
  dynamodb_table_name     = var.create_dynamodb_table == true ? aws_dynamodb_table.track_table[0].name : var.dynamodb_table_name
  enable_privatelink_dydb = var.dynamodb_privatelink == null ? false : true
}

resource "aws_dynamodb_table" "track_table" {
  count = var.create_dynamodb_table == true ? 1 : 0

  name         = var.dynamodb_table_name == "" ? "${var.module_prefix}fgt_asg_track_table" : "${var.module_prefix}${var.dynamodb_table_name}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "Category"

  attribute {
    name = "Category"
    type = "S"
  }
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "dynamodb", {})
  )
}

resource "aws_dynamodb_table_item" "user_config" {
  count      = var.create_dynamodb_table == true && var.user_conf != "" ? 1 : 0
  table_name = local.dynamodb_table_name
  hash_key   = "Category"

  item       = <<ITEM
{
  "Category": {"S": "user_config"},
  "content": {"S": "${base64encode(var.user_conf)}"}
}
ITEM
  depends_on = [aws_dynamodb_table.track_table]
}

resource "aws_vpc_endpoint" "dynamodb" {
  count = local.enable_privatelink_dydb ? 1 : 0

  vpc_id             = var.dynamodb_privatelink.vpc_id
  service_name       = "com.amazonaws.${var.dynamodb_privatelink.region}.dynamodb"
  subnet_ids         = var.dynamodb_privatelink.privatelink_subnet_ids
  vpc_endpoint_type  = "Interface"
  security_group_ids = var.dynamodb_privatelink.privatelink_security_groups
}

resource "aws_s3_bucket" "fgt_lic" {
  count = var.lic_s3_name != null ? 0 : 1

  bucket = "${var.module_prefix}fgt-asg-lic-${uuid()}"
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "s3", {})
  )
  lifecycle {
    ignore_changes = [
      bucket,
    ]
  }
}

resource "aws_s3_object" "fgt_lic" {
  for_each = local.lic_file_set

  bucket = aws_s3_bucket.fgt_lic[0].id
  key    = each.value
  source = "${local.lic_folder}/${each.value}"
  etag   = filemd5("${local.lic_folder}/${each.value}")
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "s3", {})
  )
}

resource "aws_s3_object" "fgt_lic_track_file" {
  count = var.lic_s3_name != null ? 0 : 1

  bucket  = aws_s3_bucket.fgt_lic[0].id
  key     = "asg-fgt-lic-track.json"
  content = "{}"
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "s3", {})
  )
  lifecycle {
    ignore_changes = [
      tags,
    ]
  }
}

resource "aws_s3_object" "fgt_intf_track_file" {
  count = var.lic_s3_name != null ? 0 : 1

  bucket  = aws_s3_bucket.fgt_lic[0].id
  key     = "intf_track.json"
  content = "{}"
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "s3", {})
  )
  lifecycle {
    ignore_changes = [
      tags,
    ]
  }
}

resource "aws_lambda_layer_version" "lambda_layer_requests" {
  filename   = "${path.module}/requests_layer.zip"
  layer_name = "lambda_layer_requests"

  compatible_runtimes = ["python3.12"]
}

resource "aws_lambda_function" "fgt_asg_lambda" {
  filename         = data.archive_file.lambda_public.output_path
  function_name    = "${local.asg_name}_fgt-asg-lambda"
  role             = aws_iam_role.iam_for_lambda.arn
  handler          = "fgt-asg-lambda.lambda_handler"
  source_code_hash = data.archive_file.lambda_public.output_base64sha256
  runtime          = "python3.12"
  timeout          = var.lambda_timeout
  layers = [
    aws_lambda_layer_version.lambda_layer_requests.arn
  ]

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.fgt_asg_lambda.name
  }

  environment {
    variables = {
      internal_lambda_name           = "${local.asg_name}_fgt-asg-lambda-internal"
      asg_name                       = local.asg_name
      network_interfaces             = jsonencode(var.network_interfaces)
      lic_s3_name                    = local.lic_s3_name
      need_license                   = var.license_type == "byol" ? true : false
      fmg_integration                = jsonencode(var.fmg_integration)
      gwlb_ips                       = jsonencode(var.gwlb_ips)
      fgt_multi_vdom                 = var.fgt_multi_vdom
      create_geneve_for_all_az       = var.create_geneve_for_all_az
      user_conf_s3                   = jsonencode(var.user_conf_s3)
      enable_privatelink_dydb        = local.enable_privatelink_dydb
      dynamodb_table_name            = local.enable_privatelink_dydb ? null : local.dynamodb_table_name
      enable_fgt_system_autoscale    = var.enable_fgt_system_autoscale
      fgt_system_autoscale_psksecret = var.fgt_system_autoscale_psksecret
      fortiflex_username             = var.fortiflex_username
      fortiflex_password             = var.fortiflex_password
      fortiflex_refresh_token        = var.fortiflex_refresh_token
      fortiflex_sn_list              = jsonencode(var.fortiflex_sn_list)
      fortiflex_configid_list        = jsonencode(var.fortiflex_configid_list)
      az_name_map                    = jsonencode(var.az_name_map)
      mgmt_intf_index                = var.mgmt_intf_index
      primary_scalein_protection     = var.enable_fgt_system_autoscale && var.primary_scalein_protection
    }
  }

  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "lambda", {})
  )
  depends_on = [
    aws_cloudwatch_log_group.fgt_asg_lambda,
  ]
}

resource "aws_lambda_function" "fgt_asg_lambda_internal" {
  filename         = data.archive_file.lambda_private.output_path
  function_name    = "${local.asg_name}_fgt-asg-lambda-internal"
  role             = aws_iam_role.iam_for_lambda.arn
  handler          = "fgt-asg-lambda-internal.lambda_handler"
  source_code_hash = data.archive_file.lambda_private.output_base64sha256
  runtime          = "python3.12"
  timeout          = var.lambda_timeout
  layers = [
    aws_lambda_layer_version.lambda_layer_requests.arn
  ]

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.fgt_asg_lambda_internal.name
  }

  vpc_config {
    subnet_ids = distinct(concat(
      concat([for intf_name, intf_info in var.network_interfaces : values(intf_info["subnet_id_map"]) if(intf_info["device_index"] == var.mgmt_intf_index && lookup(intf_info, "subnet_id_map", null) != null)]...),
      local.enable_privatelink_dydb ? var.dynamodb_privatelink.privatelink_subnet_ids : []
    ))
    security_group_ids = distinct(concat(
      concat([for intf_name, intf_info in var.network_interfaces : intf_info["security_groups"] if(intf_info["device_index"] == var.mgmt_intf_index && lookup(intf_info, "security_groups", null) != null)]...),
      local.enable_privatelink_dydb ? var.dynamodb_privatelink.privatelink_security_groups : []
    ))
  }

  environment {
    variables = {
      fgt_password          = var.fgt_password
      fgt_login_port_number = var.fgt_login_port_number
      dynamodb_table_name   = local.enable_privatelink_dydb ? local.dynamodb_table_name : null
      dydb_endpoint_url     = local.enable_privatelink_dydb ? aws_vpc_endpoint.dynamodb[0].dns_entry[0]["dns_name"] : null
    }
  }

  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "lambda", {})
  )
  depends_on = [
    aws_cloudwatch_log_group.fgt_asg_lambda_internal,
  ]
}

resource "aws_cloudwatch_log_group" "fgt_asg_lambda" {
  name = "/aws/lambda/${local.asg_name}_fgt-asg-lambda"
}

resource "aws_cloudwatch_log_group" "fgt_asg_lambda_internal" {
  name = "/aws/lambda/${local.asg_name}_fgt-asg-lambda-internal"
}

resource "aws_lambda_permission" "lambda_permission" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fgt_asg_lambda.function_name
  principal     = "events.amazonaws.com"
}

resource "aws_cloudwatch_event_rule" "fgt_asg_launch" {
  name        = "${local.asg_name}_fgt_asg_launch"
  description = "Cloudwatch event rule for FortiGate Auto Scaling Group instance launch."

  event_pattern = jsonencode({
    source = [
      "aws.autoscaling"
    ],
    detail-type = [
      "EC2 Instance-launch Lifecycle Action",
      "EC2 Instance Launch Successful"
    ],
    detail = {
      AutoScalingGroupName = [local.asg_name]
    }
  })
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "cloudwatch", {})
  )
}

resource "aws_cloudwatch_event_target" "fgt_asg_launch" {
  rule      = aws_cloudwatch_event_rule.fgt_asg_launch.name
  target_id = "${local.asg_name}_fgt_asg_launch_target"
  arn       = aws_lambda_function.fgt_asg_lambda.arn
}

resource "aws_cloudwatch_event_rule" "fgt_asg_terminate" {
  name        = "${local.asg_name}_fgt_asg_terminate"
  description = "Cloudwatch event rule for FortiGate Auto Scaling Group instance terminate."

  event_pattern = jsonencode({
    source = [
      "aws.autoscaling"
    ],
    detail-type = [
      "EC2 Instance-terminate Lifecycle Action",
      "EC2 Instance Terminate Successful"
    ],
    detail = {
      AutoScalingGroupName = [local.asg_name]
    }
  })
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "cloudwatch", {})
  )
}

resource "aws_cloudwatch_event_target" "fgt_asg_terminate" {
  rule      = aws_cloudwatch_event_rule.fgt_asg_terminate.name
  target_id = "${local.asg_name}_fgt_asg_terminate_target"
  arn       = aws_lambda_function.fgt_asg_lambda.arn
}
