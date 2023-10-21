output "tgw" {
  value = local.tgw
}

output "tgw_attachments" {
  value = {
    for tgw_attachment in aws_ec2_transit_gateway_vpc_attachment.tgw_attachments :
    tgw_attachment.tags.Name => tgw_attachment.id
  }
}
