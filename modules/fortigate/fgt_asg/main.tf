locals {
  ami_search_string = var.license_type == "byol" ? "FortiGate-VM64-AWS build*${var.fgt_version}*" : "FortiGate-VM64-AWSONDEMAND build*${var.fgt_version}*"
}

data "aws_ami" "fgt_ami" {
  most_recent = true
  owners      = ["aws-marketplace"]

  filter {
    name   = "name"
    values = [local.ami_search_string]
  }
}

locals {
  vars = {
    fgt_hostname       = var.fgt_hostname
    fgt_password       = var.fgt_password
    fgt_multi_vdom     = var.fgt_multi_vdom
    network_interfaces = var.network_interfaces
  }
  fgt_userdata = templatefile("${path.module}/fgt-userdata.tftpl", local.vars)
}


## FortiGate instance launch template
resource "aws_launch_template" "fgt" {
  name                   = var.template_name == "" ? null : var.template_name
  image_id               = data.aws_ami.fgt_ami.id
  instance_type          = var.instance_type
  key_name               = var.keypire_name
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
  name                      = var.asg_name
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
    name                 = "fgt_asg_launch_hook"
    default_result       = "CONTINUE"
    heartbeat_timeout    = 60
    lifecycle_transition = "autoscaling:EC2_INSTANCE_LAUNCHING"
  }

  initial_lifecycle_hook {
    name                 = "fgt_asg_terminate_hook"
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
  name               = "iam_for_lambda-${uuid()}"
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
  name = "lambda_iam_policy"
  role = aws_iam_role.iam_for_lambda.id

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
  lic_folder          = var.lic_folder_path == null ? "" : trimsuffix(var.lic_folder_path, "/")
  lic_file_set        = var.lic_s3_name != null ? toset([]) : var.lic_folder_path == null ? toset([]) : fileset(var.lic_folder_path, "*")
  lic_s3_name         = var.lic_s3_name != null ? var.lic_s3_name : aws_s3_bucket.fgt_lic[0].id
  dynamodb_table_name = var.dynamodb_table_name != "" ? var.dynamodb_table_name : aws_dynamodb_table.track_table[0].name
}

resource "aws_dynamodb_table" "track_table" {
  count = var.create_dynamodb_table == true ? 1 : 0

  name         = "fgt_asg_track_table"
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

resource "aws_s3_bucket" "fgt_lic" {
  count = var.lic_s3_name != null ? 0 : 1

  bucket = "fgt-asg-lic-${uuid()}"
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

  compatible_runtimes = ["python3.8"]
}

resource "aws_lambda_function" "fgt_asg_lambda" {
  filename         = data.archive_file.lambda_public.output_path
  function_name    = "fgt-asg-lambda_${var.asg_name}"
  role             = aws_iam_role.iam_for_lambda.arn
  handler          = "fgt-asg-lambda.lambda_handler"
  source_code_hash = data.archive_file.lambda_public.output_base64sha256
  runtime          = "python3.8"
  timeout          = var.lambda_timeout
  layers = [
    aws_lambda_layer_version.lambda_layer_requests.arn
  ]

  environment {
    variables = {
      internal_lambda_name           = "fgt-asg-lambda-internal_${var.asg_name}"
      asg_name                       = var.asg_name
      network_interfaces             = jsonencode(var.network_interfaces)
      lic_s3_name                    = local.lic_s3_name
      need_license                   = var.license_type == "byol" ? true : false
      gwlb_ips                       = jsonencode(var.gwlb_ips)
      fgt_multi_vdom                 = var.fgt_multi_vdom
      create_geneve_for_all_az       = var.create_geneve_for_all_az
      user_conf                      = var.user_conf
      user_conf_s3                   = jsonencode(var.user_conf_s3)
      dynamodb_table_name            = var.dynamodb_table_name
      enable_fgt_system_autoscale    = var.enable_fgt_system_autoscale
      fgt_system_autoscale_psksecret = var.fgt_system_autoscale_psksecret
      fortiflex_refresh_token        = var.fortiflex_refresh_token
      fortiflex_sn_list              = jsonencode(var.fortiflex_sn_list)
      fortiflex_configid_list        = jsonencode(var.fortiflex_configid_list)
      az_name_map                    = jsonencode(var.az_name_map)
    }
  }

  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "lambda", {})
  )
}

resource "aws_lambda_function" "fgt_asg_lambda_internal" {
  filename         = data.archive_file.lambda_private.output_path
  function_name    = "fgt-asg-lambda-internal_${var.asg_name}"
  role             = aws_iam_role.iam_for_lambda.arn
  handler          = "fgt-asg-lambda-internal.lambda_handler"
  source_code_hash = data.archive_file.lambda_private.output_base64sha256
  runtime          = "python3.8"
  timeout          = var.lambda_timeout
  layers = [
    aws_lambda_layer_version.lambda_layer_requests.arn
  ]

  vpc_config {
    subnet_ids         = concat([for intf_name, intf_info in var.network_interfaces : values(intf_info["subnet_id_map"]) if lookup(intf_info, "subnet_id_map", null) != null]...)
    security_group_ids = concat([for intf_name, intf_info in var.network_interfaces : intf_info["security_groups"] if lookup(intf_info, "security_groups", null) != null]...)
  }

  environment {
    variables = {
      fgt_password          = var.fgt_password
      fgt_login_port_number = var.fgt_login_port_number
    }
  }

  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "lambda", {})
  )
}

resource "aws_lambda_permission" "lambda_permission" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fgt_asg_lambda.function_name
  principal     = "events.amazonaws.com"
}

resource "aws_cloudwatch_event_rule" "fgt_asg_launch" {
  name        = "fgt_asg_launch_${var.asg_name}"
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
      AutoScalingGroupName = [var.asg_name]
    }
  })
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "cloudwatch", {})
  )
}

resource "aws_cloudwatch_event_target" "fgt_asg_launch" {
  rule      = aws_cloudwatch_event_rule.fgt_asg_launch.name
  target_id = "fgt_asg_launch_target_${var.asg_name}"
  arn       = aws_lambda_function.fgt_asg_lambda.arn
}

resource "aws_cloudwatch_event_rule" "fgt_asg_terminate" {
  name        = "fgt_asg_terminate_${var.asg_name}"
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
      AutoScalingGroupName = [var.asg_name]
    }
  })
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "cloudwatch", {})
  )
}

resource "aws_cloudwatch_event_target" "fgt_asg_terminate" {
  rule      = aws_cloudwatch_event_rule.fgt_asg_terminate.name
  target_id = "fgt_asg_terminate_target_${var.asg_name}"
  arn       = aws_lambda_function.fgt_asg_lambda.arn
}