variable "hostinger_ip" {
  description = "Public IP Address or Domain of your Hostinger VPS"
  type        = string
  default     = "elevateiq-softtech.com"
}

variable "hostinger_user" {
  description = "Hostinger VPS Root SSH Username"
  type        = string
  default     = "root"
}

variable "hostinger_password" {
  description = "Hostinger VPS Root SSH Password"
  type        = string
  sensitive   = true
}

variable "database_url" {
  description = "Neon Serverless PostgreSQL Database Connection URI (Optional: uses VPS .env if omitted)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "domain_name" {
  description = "Primary Production Domain Name"
  type        = string
  default     = "elevateiq-softtech.com"
}
