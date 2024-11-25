locals {
  chip_type         = strcontains(split(".", var.instance_type)[0], "g") ? "ARM" : "Intel"
  product_code      = var.license_type == "byol" ? (local.chip_type == "ARM" ? "33ndn84xbrajb9vmu5lxnfpjq" : "dlaioq277sglm5mw1y1dmeuqa") : (local.chip_type == "ARM" ? "8gc40z1w65qjt61p9ps88057n" : "2wqkpek696qhdeo7lbbjncqli")
  ami_search_string = var.license_type == "byol" ? "FortiGate-VM*(${var.fgt_version}*" : "FortiGate-VM*(${var.fgt_version}*"
  fos_ami_id        = var.ami_id != "" ? var.ami_id : data.aws_ami.fgt_ami.id
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

resource "aws_network_interface" "fgt_intfs" {
  for_each = var.network_interfaces

  subnet_id         = each.value.subnet_id
  security_groups   = lookup(each.value, "security_groups", null)
  source_dest_check = lookup(each.value, "source_dest_check", null)
  private_ips       = lookup(each.value, "private_ips", null)
  description       = lookup(each.value, "description", null)
  tags = merge(
    {
      Name = "${var.module_prefix}${each.key}"
    },
    lookup(var.tags, "general", {}),
    lookup(var.tags, "interface", {})
  )
}

resource "aws_eip" "fgt_eips" {
  for_each = { for k, v in var.network_interfaces : k => v if(lookup(v, "enable_public_ip", false) || lookup(v, "existing_eip_id", "") != "") }

  domain                    = "vpc"
  network_interface         = aws_network_interface.fgt_intfs[each.key].id
  public_ipv4_pool          = lookup(each.value, "public_ipv4_pool", "amazon")
  associate_with_private_ip = element(split("/", aws_network_interface.fgt_intfs[each.key].private_ip), 0)
  tags = merge(
    {
      Name = each.key
    },
    lookup(var.tags, "general", {}),
    lookup(var.tags, "eip", {})
  )
}

locals {
  vars = {
    fgt_hostname         = var.fgt_hostname
    fgt_password         = var.fgt_password
    fgt_multi_vdom       = var.fgt_multi_vdom
    network_interfaces   = var.network_interfaces
    user_conf            = var.user_conf
    fgt_license          = var.license_type == "byol" ? file("${var.lic_file_path}") : ""
    fgt_admin_https_port = var.fgt_admin_https_port
    fgt_admin_ssh_port   = var.fgt_admin_ssh_port
    fortiflex_sn         = var.fortiflex_sn
  }
  fgt_userdata = templatefile("${path.module}/fgt-userdata.tftpl", local.vars)
}

resource "aws_instance" "fgt" {
  ami               = data.aws_ami.fgt_ami.id
  instance_type     = var.instance_type
  availability_zone = var.availability_zone == "" ? null : var.availability_zone
  key_name          = var.keypair_name
  user_data         = local.fgt_userdata
  dynamic "network_interface" {
    for_each = { for k, v in var.network_interfaces : k => v if v.device_index == 0 }

    content {
      device_index         = 0
      network_interface_id = aws_network_interface.fgt_intfs[network_interface.key].id
    }
  }

  tags = merge(
    var.instance_name == "" ? {} : { Name = "${var.module_prefix}${var.instance_name}" },
    lookup(var.tags, "general", {}),
    lookup(var.tags, "instance", {})
  )
}

resource "aws_eip_association" "fgt" {
  for_each = { for k, v in var.network_interfaces : k => v if lookup(v, "existing_eip_id", "") != "" || lookup(v, "enable_public_ip", false) }

  allocation_id        = lookup(each.value, "existing_eip_id", "") != "" ? each.value.existing_eip_id : aws_eip.fgt_eips[each.key].id
  network_interface_id = aws_network_interface.fgt_intfs[each.key].id

  depends_on = [
    aws_instance.fgt
  ]
}


resource "aws_network_interface_attachment" "fgt" {
  for_each = { for k, v in var.network_interfaces : k => v if v.device_index > 0 }

  instance_id          = aws_instance.fgt.id
  network_interface_id = aws_network_interface.fgt_intfs[each.key].id
  device_index         = each.value.device_index
}
