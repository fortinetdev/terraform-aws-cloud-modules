## Gateway Load Balancer
resource "aws_lb" "gwlb" {
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
resource "aws_lb_target_group" "gwlb_tgp" {
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
  for_each = var.gwlb_tg_attachments

  target_group_arn  = aws_lb_target_group.gwlb_tgp.arn
  target_id         = each.value.tgp_target_id
  port              = lookup(each.value, "tgp_attach_port", null)
  availability_zone = lookup(each.value, "tgp_attach_availability_zone", null)
}

## Gateway Load balancer Listener
resource "aws_lb_listener" "gwlb_ln" {
  load_balancer_arn = aws_lb.gwlb.arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.gwlb_tgp.arn
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
  count = length(var.subnets)
  filter {
    name   = "description"
    values = ["ELB gwy/${aws_lb.gwlb.name}/*"]
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
resource "aws_vpc_endpoint_service" "gwlb_ep_service" {
  acceptance_required        = false
  gateway_load_balancer_arns = [aws_lb.gwlb.arn]
  tags = merge(
    {
      Name = var.gwlb_ep_service_name
    },
    lookup(var.tags, "general", {}),
    lookup(var.tags, "gwlb_ep_service", {})
  )
}

resource "aws_vpc_endpoint" "gwlb_endps" {
  for_each = var.gwlb_endps

  vpc_id            = each.value.vpc_id
  subnet_ids        = toset([each.value.subnet_id])
  service_name      = aws_vpc_endpoint_service.gwlb_ep_service.service_name
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