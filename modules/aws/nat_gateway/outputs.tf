output "nat_gateway" {
  value = local.ngw
}

output "availability_zone" {
  value = data.aws_subnet.ngw_subnet == null ? null : data.aws_subnet.ngw_subnet[0].availability_zone
}