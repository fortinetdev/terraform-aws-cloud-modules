## Variable with prefix 'existing_' is null means no related existing resource, then will check related name/id and create new one if configured;
## Variable with prefix 'existing_' is not null means have related existing resource, then if no content means ignore the resource, if has content means use the existing resource.
locals {
  gwlb            = var.existing_gwlb == null ? (var.gwlb_name == "" ? null : aws_lb.gwlb[0]) : length(coalesce(var.existing_gwlb, {})) == 0 ? null : data.aws_lb.gwlb[0]
  gwlb_tgp        = var.existing_gwlb != null && length(coalesce(var.existing_gwlb, {})) == 0 ? null : var.existing_gwlb_tgp == null ? (var.tgp_name == "" ? null : aws_lb_target_group.gwlb_tgp[0]) : length(coalesce(var.existing_gwlb_tgp, {})) == 0 ? null : data.aws_lb_target_group.gwlb_tgp[0]
  gwlb_ep_service = var.existing_gwlb != null && length(coalesce(var.existing_gwlb, {})) == 0 ? null : var.existing_gwlb_ep_service == null ? (var.gwlb_ep_service_name == "" ? null : aws_vpc_endpoint_service.gwlb_ep_service[0]) : length(coalesce(var.existing_gwlb_ep_service, {})) == 0 ? null : data.aws_vpc_endpoint_service.gwlb_ep_service[0]
}

## Gateway Load Balancer
data "aws_lb" "gwlb" {
  count = var.existing_gwlb != null && length(coalesce(var.existing_gwlb, {})) > 0 ? 1 : 0

  arn  = lookup(var.existing_gwlb, "arn", null)
  name = lookup(var.existing_gwlb, "name", null)
  tags = lookup(var.existing_gwlb, "tags", null)
}

resource "aws_lb" "gwlb" {
  count = var.existing_gwlb == null && var.gwlb_name != "" ? 1 : 0

  name                             = var.gwlb_name
  load_balancer_type               = "gateway"
  enable_cross_zone_load_balancing = var.enable_cross_zone_load_balancing
  subnets                          = var.subnets
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "gwlb", {})
  )

  lifecycle {
    create_before_destroy = true
  }
}

## Target Group
data "aws_lb_target_group" "gwlb_tgp" {
  count = var.existing_gwlb_tgp != null && length(coalesce(var.existing_gwlb_tgp, {})) > 0 ? 1 : 0

  arn  = lookup(var.existing_gwlb_tgp, "arn", null)
  name = lookup(var.existing_gwlb_tgp, "name", null)
  tags = lookup(var.existing_gwlb_tgp, "tags", null)
}

resource "aws_lb_target_group" "gwlb_tgp" {
  count = var.existing_gwlb_tgp == null && var.tgp_name != "" ? 1 : 0

  name                 = var.tgp_name
  vpc_id               = var.vpc_id
  target_type          = var.target_type
  deregistration_delay = var.deregistration_delay
  protocol             = "GENEVE"
  port                 = "6081"

  health_check {
    enabled             = lookup(var.health_check, "enabled", null)
    healthy_threshold   = lookup(var.health_check, "healthy_threshold", null)
    interval            = lookup(var.health_check, "interval", null)
    path                = lookup(var.health_check, "path", null)
    port                = lookup(var.health_check, "port", null)
    protocol            = lookup(var.health_check, "protocol", null)
    timeout             = lookup(var.health_check, "timeout", null)
    unhealthy_threshold = lookup(var.health_check, "unhealthy_threshold", null)
  }
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "tgp", {})
  )
}

resource "aws_lb_target_group_attachment" "gwlb_tgp_a" {
  for_each = local.gwlb_tgp == null ? {} : var.gwlb_tg_attachments

  target_group_arn  = local.gwlb_tgp.arn
  target_id         = each.value.tgp_target_id
  port              = lookup(each.value, "tgp_attach_port", null)
  availability_zone = lookup(each.value, "tgp_attach_availability_zone", null)
}

## Gateway Load balancer Listener
resource "aws_lb_listener" "gwlb_ln" {
  count = local.gwlb == null || local.gwlb_tgp == null ? 0 : 1

  load_balancer_arn = local.gwlb.arn
  default_action {
    type             = "forward"
    target_group_arn = local.gwlb_tgp.arn
  }

  tags = merge(
    {
      Name = var.gwlb_ln_name
    },
    lookup(var.tags, "general", {}),
    lookup(var.tags, "gwlb_ln", {})
  )
}

## Get Gateway Load balancer IP
data "aws_network_interface" "gwlb_intfs" {
  count = local.gwlb == null ? 0 : length(var.subnets)
  filter {
    name   = "description"
    values = ["ELB gwy/${aws_lb.gwlb[0].name}/*"]
  }
  filter {
    name   = "vpc-id"
    values = ["${var.vpc_id}"]
  }
  filter {
    name   = "interface-type"
    values = ["gateway_load_balancer"]
  }
  filter {
    name   = "subnet-id"
    values = [var.subnets[count.index]]
  }
}

## Gateway Load Balancer Endpoint
data "aws_vpc_endpoint_service" "gwlb_ep_service" {
  count = var.existing_gwlb_ep_service != null && length(coalesce(var.existing_gwlb_ep_service, {})) > 0 ? 1 : 0

  service_name = lookup(var.existing_gwlb_ep_service, "service_name", null)
  tags         = lookup(var.existing_gwlb_ep_service, "tags", null)
  dynamic "filter" {
    for_each = lookup(var.existing_gwlb_ep_service, "filter", {})
    content {
      name   = filter.key
      values = filter.value
    }
  }
}

resource "aws_vpc_endpoint_service" "gwlb_ep_service" {
  count = var.existing_gwlb_ep_service == null && var.gwlb_ep_service_name != "" && local.gwlb != null ? 1 : 0

  acceptance_required        = false
  gateway_load_balancer_arns = [local.gwlb.arn]
  tags = merge(
    {
      Name = var.gwlb_ep_service_name
    },
    lookup(var.tags, "general", {}),
    lookup(var.tags, "gwlb_ep_service", {})
  )
}

resource "aws_vpc_endpoint" "gwlb_endps" {
  for_each = length(aws_vpc_endpoint_service.gwlb_ep_service) == 0 ? {} : var.gwlb_endps

  vpc_id            = each.value.vpc_id
  subnet_ids        = toset([each.value.subnet_id])
  service_name      = aws_vpc_endpoint_service.gwlb_ep_service[0].service_name
  vpc_endpoint_type = "GatewayLoadBalancer"
  tags = merge(
    {
      Name = each.key
    },
    lookup(var.tags, "general", {}),
    lookup(var.tags, "gwlb_endp", {})
  )

  lifecycle {
    create_before_destroy = true
  }
}