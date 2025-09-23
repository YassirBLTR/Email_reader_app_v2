# Email Reader App

A FastAPI-based web application for reading, searching, filtering, and downloading .msg email files from a server folder.

## Features

- **Email Listing**: Browse emails with pagination
- **Advanced Search**: Search by text, sender, subject, and date range
- **Email Parsing**: Parse .msg files to display readable content
- **Download Options**: Export emails in JSON or text format
- **Modern UI**: Responsive web interface with Bootstrap
- **REST API**: Complete API with interactive documentation

## Quick Start

### Prerequisites

- Python 3.8 or higher
- .msg email files in a folder

### Installation

1. **Clone or download the project**
```bash
git clone <repository-url>
cd Email_reader_app
```

2. **Create virtual environment**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env file to set EMAIL_FOLDER_PATH to your .msg files directory
```

5. **Run the application**
```bash
python run.py
```

6. **Access the application**
- Web Interface: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Configuration

Edit the `.env` file to configure:

```env
EMAIL_FOLDER_PATH=/path/to/your/msg/files
HOST=0.0.0.0
PORT=8000
DEBUG=False
MAX_DOWNLOAD_SIZE=104857600
DEFAULT_PAGE_SIZE=20
MAX_PAGE_SIZE=100
```

## API Endpoints

### Email Operations
- `GET /api/emails/` - List emails with pagination
- `POST /api/emails/search` - Search emails with filters
- `GET /api/emails/{filename}` - Get email details
- `POST /api/emails/download` - Download selected emails
- `GET /api/emails/stats/summary` - Get email statistics

### System
- `GET /health` - Health check
- `GET /docs` - API documentation
- `GET /` - Web interface

## Testing with Postman

1. Import the collection: `postman/email_reader_collection.json`
2. Set environment variables:
   - `base_url`: http://localhost:8000
   - `email_filename`: actual .msg filename for testing
3. Run the requests to test all endpoints

## Deployment

### Rocky Linux Server

See detailed deployment guide: `deployment/README.md`

### Docker

```bash
# Build and run with Docker Compose
cd deployment/docker
docker-compose up -d
```

## Project Structure

```
Email_reader_app/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── models/              # Pydantic models
│   ├── routers/             # API endpoints
│   ├── services/            # Business logic
│   ├── utils/               # Utilities (MSG parser)
│   └── static/              # Frontend files
├── deployment/              # Deployment configurations
├── postman/                 # API test collection
├── requirements.txt         # Python dependencies
└── run.py                   # Development server
```

## Features Overview

### Web Interface
- **Search Bar**: Full-text search across subject, sender, recipients
- **Filters**: Date range, sender, subject filters
- **Email List**: Paginated table with sorting
- **Email Viewer**: Modal with full email content and attachments
- **Bulk Download**: Select multiple emails for download
- **Responsive Design**: Works on desktop and mobile

### API Features
- **Pagination**: Efficient handling of large email collections
- **Search**: Multiple filter combinations
- **File Formats**: JSON and text export options
- **Error Handling**: Comprehensive error responses
- **Documentation**: Interactive Swagger UI

### Email Processing
- **MSG Parsing**: Extract all email metadata and content
- **Attachment Handling**: List and optionally include attachments
- **Content Display**: Both HTML and plain text body support
- **Header Information**: Complete email headers available

## Development

### Running in Development Mode
```bash
python run.py
# or
uvicorn app.main:app --reload
```

### Adding New Features
1. Add models in `app/models/`
2. Implement services in `app/services/`
3. Create API endpoints in `app/routers/`
4. Update frontend in `app/static/`

## Troubleshooting

### Common Issues

**Email folder not found**
- Verify EMAIL_FOLDER_PATH in .env file
- Check folder permissions

**MSG parsing errors**
- Ensure .msg files are valid Outlook message files
- Check file permissions

**Port already in use**
- Change PORT in .env file
- Kill existing processes on port 8000

**Permission denied**
- Run with appropriate user permissions
- Check file and folder ownership

## Security Considerations

- Run with minimal user privileges
- Restrict access to email folder
- Use HTTPS in production
- Implement authentication if needed
- Regular security updates

## Performance Tips

- Use pagination for large email collections
- Index email folder for faster searches
- Configure appropriate timeouts
- Monitor memory usage with large attachments
- Use reverse proxy (Nginx) in production

## License

This project is provided as-is for educational and business use.

## Support

For issues and questions:
1. Check the logs for error details
2. Verify configuration settings
3. Test API endpoints with Postman
4. Review deployment documentation
