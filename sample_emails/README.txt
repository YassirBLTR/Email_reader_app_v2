This is a sample email folder for local development and testing.

Since the actual .msg email files exist on your server, this folder serves as a placeholder for local development.

For testing the application locally:
1. You can place sample .msg files here if available
2. Or test with the server deployment where actual files exist

When deploying to your server:
1. Update the EMAIL_FOLDER_PATH in .env to point to your actual email folder
2. Examples:
   - EMAIL_FOLDER_PATH=/var/emails
   - EMAIL_FOLDER_PATH=/home/username/email_files
   - EMAIL_FOLDER_PATH=/srv/emails

The application will gracefully handle the case when no email files are found and display appropriate messages.
