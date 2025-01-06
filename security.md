# Security Policy

This project values the security of its users and the integrity of the software.  We appreciate your efforts in responsibly disclosing any vulnerabilities you may discover.

## Supported Versions

Currently, only the latest version of the project receives active security updates.  While older versions may still function, they are not guaranteed to be secure and are not supported.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| *       | :x:                |  *(All other versions)*


## Reporting a Vulnerability

To report a security vulnerability, please follow these steps:

1. **Do Not Publicly Disclose:**  Avoid disclosing the vulnerability publicly until it has been addressed.
2. **Contact Us:** Please report the vulnerability by creating a new [GitHub issue ([https://github.com/your_username/your-repo-name/issues/new](https://github.com/Grab-your-parachutes/Twitch-ChatGpt4-LittleNavMap-integrated-chatbot.git))]   and selecting the "Security vulnerability" option.  Make sure to provide a detailed description of the vulnerability, including:
    * Steps to reproduce the issue.
    * The potential impact of the vulnerability.
    * Any relevant code snippets or proof-of-concept demonstrations (if possible, share these privately).
3. **Confidentiality:** We will treat your report with strict confidentiality.
4. **Response Time:** We strive to respond to vulnerability reports within 72 hours. We'll acknowledge receipt of your report and provide updates on the progress of our investigation.
5. **Resolution:**  Once a vulnerability is confirmed, we will work diligently to develop and release a fix.  We will coordinate with you regarding the disclosure timeline and any potential public announcements.
6. **Responsible Disclosure:**  We encourage responsible disclosure practices. After the vulnerability has been patched, we may publicly acknowledge your contribution (with your permission).

## Security Best Practices (for users)

* **Keep Dependencies Up-to-Date:** Regularly update the bot's dependencies to patch any known vulnerabilities in underlying libraries.  Use `pip freeze > requirements.txt` after updating to ensure your `requirements.txt` file is current.
* **Secure Your Credentials:** Protect your Twitch OAuth token, OpenAI API key, MongoDB credentials, and other sensitive information. Store them securely, preferably using environment variables, and never commit them to version control.
* **Regularly Review Logs:** Monitor the bot's logs for any suspicious activity.
* **Use a Strong Password for MongoDB:** Choose a strong and unique password for your MongoDB instance to prevent unauthorized access.
* **Limit Bot Permissions:** Grant the bot only the necessary permissions on your Twitch channel to minimize the potential impact of any security breaches.


We appreciate your help in keeping this project secure!
