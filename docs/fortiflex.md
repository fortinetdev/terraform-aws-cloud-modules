# How to get FortiFlex credential

## Prerequest

An FortiCloud account, check [here](https://docs.fortinet.com/document/forticloud/latest/forticloud-account/227089) to create an account.

## Create FortiFlex credential

1. Create an API User for the account in IAM. For more information see [here](https://docs.fortinet.com/document/forticloud/21.2.0/identity-access-management-iam/282341/adding-an-api-user). 

2. Give desired permission (Admin, ReadWrite, ReadOnly) for FortiFlex to the newly created or existing API User. Actions that involve changing or creating data (such as creating a new Configuration or updating an entitlement) will require ReadWrite permission or above. You can provide the username/passord to the module as `fortiflex_username` and `fortiflex_password`. To create a refersh token, continue to step 3.

3. Call API at https://customerapiauth.fortinet.com/api/v1/oauth/token/ to retrieve Refresh token of variable `refresh_token` from the response. Request body should be similar to:
    ```
    {
    "username": "<API Username>",
    "password": "<API Password>",
    "client_id": "flexvm",
    "grant_type": "password"
    }
    ```
    For more information see [here](https://docs.fortinet.com/document/fortiauthenticator/6.1.2/rest-api-solution-guide/498666/oauth-server-token-oauth-token).