# 🏨 AI-Powered Hotel Management System

An AI-powered hotel management platform that combines a modern hotel booking system, AI reception, conversational booking, voice interaction, and a complete staff/admin dashboard into one integrated application.

The main goal of this project is to build an AI receptionist that is not limited to answering questions, but can actually interact with the hotel's booking system and perform real booking operations through the database.

---

## 📌 Project Overview

The **AI-Powered Hotel Management System** provides an intelligent hotel reception experience for customers and a complete management dashboard for hotel staff.

The system connects:

- 🤖 AI Receptionist
- 💬 AI Chat
- 🎙️ AI Voice
- 🏨 Room Availability
- 📅 Hotel Booking
- 🔄 Booking Modification
- ❌ Booking Cancellation
- 👥 Customer Management
- 💰 Revenue Management
- 👨‍💼 Admin Dashboard
- 🗄️ Database
- ☁️ Railway Deployment

The AI receptionist is named **Chitti** and is designed to work like a real hotel reception assistant.

---

# 🎯 Project Objective

The objective of this project is to create a complete AI-powered hotel management solution where customers can interact naturally with an AI receptionist while hotel staff can manage the complete hotel operation through an admin dashboard.

Instead of using AI only for conversation, the system connects the AI with actual hotel backend operations.

The AI can:

- Understand customer requests
- Check room availability
- Show available rooms
- Collect customer details
- Calculate booking amounts
- Create real bookings
- Modify existing bookings
- Recalculate modified booking amounts
- Cancel bookings
- Update the database
- Reflect changes in the admin dashboard

---

# ✨ Main Features

## 🤖 AI Receptionist — Chitti

The system provides an AI receptionist called **Chitti**.

Chitti can assist customers with:

- Hotel-related questions
- Room availability
- Room selection
- Booking
- Booking confirmation
- Booking modification
- Booking cancellation
- Customer details
- Adults and children information
- Multilingual conversations
- Voice interaction

The AI is designed to understand natural language instead of forcing users to follow a fixed form.

---

# 💬 AI Chat

The AI Chat interface allows customers to communicate with Chitti using normal text messages.

### Chat Capabilities

- Natural language conversation
- Hotel information
- Room availability
- Room type selection
- Date understanding
- Guest count
- Customer information collection
- Booking confirmation
- Actual database booking
- Booking modification
- Booking cancellation
- Multilingual responses
- Error handling

---

# 🏨 Room Types

The hotel currently provides four room categories.

| Room Type | Price Per Night |
|-----------|----------------:|
| Standard | ₹1,800 |
| Deluxe | ₹2,500 |
| Premium | ₹4,000 |
| Suite | ₹7,000 |

The system contains multiple rooms across these room types.

The AI checks actual room availability based on the requested dates and existing bookings.

---

# 🔎 Room Availability

When a customer requests a room, the AI collects the required information such as:

- Check-in date
- Check-out date
- Number of adults
- Number of children
- Preferred room type

The backend then checks the database for available rooms.

Example:

```text
User:
I want a Deluxe room for 2 adults.

AI:
Available Deluxe rooms:

Room 102
Room 106

Price: ₹2,500 per night
```

The customer can then select a specific room.

---

# 📅 AI Booking Workflow

The complete conversational booking process works as follows:

```text
Customer
   ↓
"I want to book a room"
   ↓
AI asks for dates and guest information
   ↓
Check room availability
   ↓
Show available rooms
   ↓
Customer selects room
   ↓
AI asks for customer details
   ↓
Name + Phone + Email
   ↓
Booking summary
   ↓
Customer confirmation
   ↓
Actual database booking
   ↓
Booking ID generated
   ↓
Admin dashboard updated
```

---

# 🧾 Booking Information

A booking contains information such as:

- Booking ID
- Customer
- Phone number
- Email
- Room
- Room type
- Check-in date
- Check-out date
- Number of nights
- Adults
- Children
- Total amount
- Booking status
- Modification status
- Creation information

---

# 💰 Dynamic Booking Calculation

The booking amount is calculated using the room price and number of nights.

```text
Total Amount =
Number of Nights × Room Price
```

For example:

```text
Deluxe Room
₹2,500 / night

Check-in:
2029-09-09

Check-out:
2029-09-11

Number of nights:
2

Total:
2 × ₹2,500 = ₹5,000
```

The calculated amount is stored in the database and displayed in the admin dashboard.

---

# 🔄 Booking Modification

Customers can modify an existing booking through the AI.

Supported modification information includes:

- Check-in date
- Check-out date
- Room
- Adults
- Children
- Customer name
- Phone number
- Email address

The system asks for confirmation before applying the modification.

After confirmation:

```text
AI
 ↓
Validate modification
 ↓
Update booking
 ↓
Recalculate total amount
 ↓
Save to database
 ↓
Admin dashboard updated
```

### Example

Original booking:

```text
Room: Deluxe 102
Check-in: 2029-09-09
Check-out: 2029-09-11

2 nights × ₹2,500
= ₹5,000
```

After modification:

```text
Room: Deluxe 102
Check-in: 2029-09-09
Check-out: 2029-09-12

3 nights × ₹2,500
= ₹7,500
```

The modified amount is reflected in the database and admin dashboard.

---

# ❌ Booking Cancellation

Customers can cancel an existing booking through the AI.

The system uses a confirmation step before cancellation.

Example:

```text
Customer:
Cancel that booking

AI:
Are you sure you want to cancel booking BK8944?

Customer:
Yes

AI:
Booking BK8944 has been successfully cancelled.
```

After cancellation:

```text
Booking Status = Cancelled
```

The cancelled booking remains visible in the admin dashboard for record keeping.

Cancelled bookings do not display active **Cancel** or **Modify** actions.

---

# 👨‍💼 Admin Dashboard

The project includes a complete staff/admin dashboard for hotel management.

The dashboard provides important hotel statistics and booking information.

## 📊 Dashboard Statistics

The dashboard displays:

- Occupancy
- Revenue
- Today's bookings
- Total bookings
- Cancelled bookings
- Modified bookings
- Available rooms
- Customers

---

# 📋 Booking Management

The Recent Bookings section provides a complete overview of hotel reservations.

The booking table includes:

- Booking ID
- Guest
- Room
- Check-in
- Check-out
- Adults
- Children
- Total
- Status
- Actions

Active bookings provide:

- Cancel
- Modify

Cancelled bookings do not provide active cancellation/modification actions.

---

# 👥 Customer Management

The admin dashboard also provides customer information.

Customer records can contain:

- Name
- Phone
- Email
- Number of bookings

Customer information is connected with the booking records stored in the database.

---

# 👨‍👩‍👧 Adults & Children

The system supports both adult and child guest counts.

A booking can store:

```text
Adults: 2
Children: 1
```

These values are available in the booking data and are displayed in the admin dashboard.

The AI also collects these values during conversational booking.

---

# 📈 Occupancy Management

The admin dashboard provides information about current room utilization, including:

```text
Occupied Rooms
Total Rooms
Occupancy Percentage
Available Rooms
```

This gives hotel staff an overview of hotel occupancy.

---

# 💵 Revenue Management

The admin dashboard displays revenue generated from applicable bookings.

Revenue is based on booking amounts stored in the database.

The dashboard can reflect changes when bookings are:

- Created
- Modified
- Cancelled

---

# 🔄 Admin ↔ AI ↔ Database Synchronization

One of the most important parts of this project is synchronization between the AI receptionist and the admin dashboard.

The complete system works as:

```text
Customer
   ↓
AI Receptionist
   ↓
Backend
   ↓
Database
   ↓
Admin Dashboard
```

For a new booking:

```text
AI Booking
     ↓
Database
     ↓
Admin Dashboard
```

For modification:

```text
AI Modification
     ↓
Database Update
     ↓
Updated Amount
     ↓
Admin Dashboard
```

For cancellation:

```text
AI Cancellation
     ↓
Database Status = Cancelled
     ↓
Admin Dashboard
```

This allows both the customer-facing AI and hotel staff dashboard to work with the same booking data.

---

# 🗄️ Database

The backend uses a relational database with SQLAlchemy ORM.

The major database entities include:

## Customer

Stores:

- Customer ID
- Name
- Phone
- Email

## Room

Stores:

- Room ID
- Room number
- Room type
- Room price
- Availability information

## Booking

Stores:

- Booking ID
- Customer ID
- Room ID
- Check-in
- Check-out
- Adults
- Children
- Total amount
- Booking status
- Modified status
- Creation information

---

# ⚙️ Backend

The backend is responsible for:

- Room availability
- Booking creation
- Booking modification
- Booking cancellation
- Customer management
- Room management
- Booking calculations
- Database operations
- AI integration
- API communication

The backend exposes API endpoints used by the frontend and AI system.

---

# 🤖 Groq AI Integration

The conversational AI is integrated using the **Groq API**.

Groq is used as the AI inference layer for the hotel receptionist.

The basic architecture is:

```text
User Message
     ↓
Frontend
     ↓
Backend
     ↓
Groq AI
     ↓
AI Response / Action
     ↓
Hotel Backend Logic
     ↓
Database
```

The AI is responsible for understanding conversational requests while the backend handles the actual hotel operations.

---

# 🧠 AI + Backend Architecture

The system separates AI conversation from actual database operations.

```text
                 CUSTOMER
                    │
          ┌─────────┴─────────┐
          │                   │
       AI CHAT             AI VOICE
          │                   │
          └─────────┬─────────┘
                    ↓
             AI RECEPTIONIST
                 CHITTI
                    ↓
                GROQ AI
                    ↓
          Conversational Logic
                    ↓
              Hotel Backend
                    ↓
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
     ROOMS      BOOKINGS    CUSTOMERS
        │           │           │
        └───────────┼───────────┘
                    ↓
                DATABASE
                    ↓
             ADMIN DASHBOARD
```

---

# 🎙️ AI Voice

The project also includes a voice-based AI receptionist.

The intended voice pipeline is:

```text
User speaks
    ↓
Speech Recognition
    ↓
Text
    ↓
AI Receptionist
    ↓
Groq AI
    ↓
AI Response
    ↓
Text-to-Speech
    ↓
Voice Response
```

The voice interface is designed to use the same booking logic as the text-based AI.

Therefore the same hotel operations can be used through voice:

- Room availability
- Booking
- Booking confirmation
- Modification
- Cancellation
- Customer information

### Current Status

The voice functionality is currently under integration and testing, with improvements being made for reliable speech recognition and AI voice responses.

---

# 🌍 Multilingual AI

Chitti is designed to support multilingual conversations.

Customers can communicate in different languages and switch languages during a conversation.

Example:

```text
User:
English

AI:
Sure, I can help you in English.
```

The system supports multilingual conversational responses while maintaining the hotel assistance workflow.

---

# 🖥️ User Interface

The application includes a professional hotel reception interface.

The reception UI contains:

- ABC Hotel branding
- AI Reception Desk
- Room type and pricing information
- AI conversation area
- Voice interaction
- Text input
- Send button
- New conversation
- Session information

The interface is designed to provide a realistic AI hotel reception experience.

---

# 🔐 Environment Variables

Sensitive API keys and configuration values are handled using environment variables.

Example:

```env
DATABASE_URL=your_database_url
GROQ_API_KEY=your_groq_api_key
```

Environment variables should be configured in the deployment platform rather than exposing secret keys inside the source code.

---

# ☁️ Deployment

The application is deployed using **Railway**.

The deployment includes:

- Frontend
- Backend
- Database connection
- Environment variables
- AI API configuration
- Production API communication

The deployed application has been tested through the production environment.

---

# 🧪 Testing

The system has been tested using different real conversational scenarios.

## ✅ Booking Test

Example:

```text
User:
I want a room

AI:
Requests dates and guest information

User:
2029-09-09 to 2029-09-11 for 2 adults and Deluxe room

AI:
Checks room availability

AI:
Shows available Deluxe rooms

User:
102

AI:
Requests name, phone and email

User:
Provides customer details

AI:
Shows booking summary

User:
Yes, confirm

AI:
Creates booking

AI:
Returns booking ID
```

---

## ✅ Modification Test

Example:

```text
User:
Modify

AI:
Identifies current booking

User:
2029-09-09 to 2029-09-12

AI:
Updates checkout date

AI:
Recalculates total amount

User:
Yes confirm

AI:
Updates booking in database
```

The updated booking is then reflected in the admin dashboard.

---

## ✅ Cancellation Test

Example:

```text
User:
Cancel that booking

AI:
Requests confirmation

User:
Yes

AI:
Booking cancelled successfully
```

The dashboard then displays the booking as:

```text
Cancelled
```

---

# 🧪 Edge Case Testing

The system has been tested around different booking scenarios including:

- Different room types
- Multiple rooms
- Different dates
- Invalid dates
- Existing reservations
- Cancelled reservations
- Modified reservations
- Different guest counts
- Adults and children
- Invalid customer details
- Fresh AI sessions
- Booking confirmation
- Booking cancellation
- Booking modification

---

# 🔁 Complete Booking Lifecycle

The complete booking lifecycle is:

```text
Room Search
     ↓
Availability Check
     ↓
Room Selection
     ↓
Customer Details
     ↓
Booking Summary
     ↓
Confirmation
     ↓
Database Booking
     ↓
Booking ID
     ↓
Admin Dashboard
```

Modification:

```text
Existing Booking
     ↓
Modification Request
     ↓
New Booking Details
     ↓
Price Recalculation
     ↓
Confirmation
     ↓
Database Update
     ↓
Admin Dashboard Update
```

Cancellation:

```text
Existing Booking
     ↓
Cancellation Request
     ↓
Confirmation
     ↓
Booking Status Updated
     ↓
Database
     ↓
Admin Dashboard Update
```

---

# 🏗️ System Architecture

The complete project architecture can be represented as:

```text
                         ┌──────────────────────┐
                         │       CUSTOMER       │
                         └──────────┬───────────┘
                                    │
                     ┌──────────────┴──────────────┐
                     │                             │
                     ▼                             ▼
              ┌─────────────┐               ┌─────────────┐
              │  AI CHAT    │               │  AI VOICE   │
              └──────┬──────┘               └──────┬──────┘
                     │                             │
                     └──────────────┬──────────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ CHITTI AI RECEPTION  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       GROQ AI        │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   HOTEL BACKEND      │
                         └──────────┬───────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
                 ▼                  ▼                  ▼
          ┌────────────┐     ┌────────────┐     ┌────────────┐
          │   ROOMS    │     │  BOOKINGS  │     │ CUSTOMERS  │
          └─────┬──────┘     └──────┬─────┘     └──────┬─────┘
                │                   │                  │
                └───────────────────┼──────────────────┘
                                    ▼
                         ┌──────────────────────┐
                         │      DATABASE        │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   ADMIN DASHBOARD    │
                         └──────────────────────┘
```

---

# 📂 Project Components

The system consists of the following major components:

```text
AI-Powered Hotel Management System
│
├── Hotel Reception Interface
│
├── AI Chat
│
├── AI Voice
│
├── Groq AI Integration
│
├── Hotel Backend
│
├── Room Management
│
├── Booking Management
│
├── Customer Management
│
├── Database
│
├── Admin Dashboard
│
└── Railway Deployment
```

---

# 🛠️ Technology Stack

## Frontend

- HTML
- CSS
- JavaScript

## Backend

- Python
- FastAPI
- SQLAlchemy
- REST APIs

## Database

- Relational Database
- SQLAlchemy ORM

## Artificial Intelligence

- Groq API
- Conversational AI
- Natural Language Processing

## Voice

- Speech Recognition
- Text-to-Speech
- Voice AI

## Deployment

- Railway
- GitHub

---

# 📊 Admin Dashboard Capabilities

The staff dashboard provides:

```text
✓ Occupancy
✓ Revenue
✓ Today's Bookings
✓ Total Bookings
✓ Cancelled Bookings
✓ Modified Bookings
✓ Available Rooms
✓ Customers
✓ Recent Bookings
✓ Booking Search
✓ New Booking
✓ Booking Modification
✓ Booking Cancellation
✓ Guest Information
✓ Adults
✓ Children
✓ Booking Status
```

---

# 🔥 What Makes This Project Different?

A traditional hotel website usually provides forms for customers to enter booking information.

This project takes a different approach by introducing an AI receptionist.

Instead of:

```text
Customer
   ↓
Form
   ↓
Submit
```

the system provides:

```text
Customer
   ↓
Natural Conversation
   ↓
AI Receptionist
   ↓
Hotel Operations
   ↓
Database
```

The AI is therefore connected to real hotel management functionality.

---

# 🎯 Core Project Concept

The central idea of this project is:

> **An AI receptionist that can actually interact with a hotel's booking system.**

Chitti is not designed only to answer questions.

It can participate in the complete hotel customer journey:

```text
Ask
 ↓
Understand
 ↓
Check Availability
 ↓
Select Room
 ↓
Collect Details
 ↓
Calculate Price
 ↓
Confirm
 ↓
Book
 ↓
Modify
 ↓
Cancel
 ↓
Synchronize With Admin
```

---

# 🚀 Current Project Status

## Completed

- ✅ Hotel reception interface
- ✅ Room types and pricing
- ✅ Room availability
- ✅ AI Chat
- ✅ Groq AI integration
- ✅ Conversational booking
- ✅ Actual database booking
- ✅ Booking ID generation
- ✅ Booking modification
- ✅ Modified amount calculation
- ✅ Booking cancellation
- ✅ Customer management
- ✅ Adults and children support
- ✅ Admin dashboard
- ✅ Booking management
- ✅ Revenue statistics
- ✅ Occupancy statistics
- ✅ Available room statistics
- ✅ Cancelled booking handling
- ✅ Modified booking tracking
- ✅ Admin ↔ Database synchronization
- ✅ AI ↔ Database booking flow
- ✅ Railway deployment
- 🔄 Voice AI integration/testing

---

# 🔮 Future Improvements

Possible future improvements include:

- More reliable voice recognition
- Improved text-to-speech responses
- Advanced multilingual voice support
- Payment gateway integration
- Email booking confirmations
- SMS notifications
- Authentication and role-based access
- Advanced hotel analytics
- Hotel FAQ/RAG system
- Advanced AI agents
- Better production scalability
- More advanced staff management
- Online payment support

---

# 📸 Screenshots

Screenshots of the application will be added here.

### 🏠 Hotel Reception

![Hotel Reception](screenshots/reception.png)

### 👨‍💼 Admin Dashboard

![Admin Dashboard](screenshots/admin-dashboard.png)

### 🛏️ Room Management

![Room Management](screenshots/room-management.png)

### 📋 Booking Management

![Booking Management](screenshots/booking-management.png)

### 💬 AI Chat

![AI Chat](screenshots/ai-chat.png)

### 📅 AI Booking Confirmation

![AI Booking Confirmation](screenshots/ai-booking-confirmation.png)

### 🎙️ AI Voice

![AI Voice](screenshots/ai-voice.png)

> **Note:** Add the corresponding screenshot files to a `screenshots/` folder in the repository before these images will appear on GitHub.

---

# 🔗 Project Links

- **GitHub Repository:** https://github.com/rahulsambari341-ux/AI-Powered-Hotel-Management-System
- **Live Demo:** Add the final Railway deployment URL here

---

# ⚙️ Installation

## 1. Clone the Repository

```bash
git clone https://github.com/rahulsambari341-ux/AI-Powered-Hotel-Management-System.git
```

## 2. Open the Project

```bash
cd AI-Powered-Hotel-Management-System
```

## 3. Create a Virtual Environment

```bash
python -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

## 4. Install Dependencies

```bash
pip install -r requirements.txt
```

## 5. Configure Environment Variables

Create a `.env` file and configure the required environment variables.

```env
DATABASE_URL=your_database_url
GROQ_API_KEY=your_groq_api_key
```

## 6. Run the Backend

Run the FastAPI application using the project's configured startup command.

## 7. Open the Frontend

Open the frontend application through the configured local server/browser setup.

---

# 🔐 Security

API keys and database credentials should always be stored using environment variables.

Do not commit:

```text
.env
API Keys
Database passwords
Secret credentials
```

to GitHub.

---

# 📌 Example Booking

A complete booking can look like:

```text
Booking ID: BK8944

Guest:
Eswar

Phone:
9090909090

Email:
eswar@gmail.com

Room:
102

Room Type:
Deluxe

Check-in:
2029-09-09

Check-out:
2029-09-12

Adults:
2

Children:
0

Total:
₹7,500

Status:
Confirmed
```

---

# 📌 Example Admin Dashboard Flow

```text
Customer books Room 102
        ↓
Booking stored in database
        ↓
Admin dashboard displays booking
        ↓
Customer modifies checkout date
        ↓
Booking amount recalculated
        ↓
Database updated
        ↓
Admin dashboard displays new amount
        ↓
Customer cancels booking
        ↓
Status becomes Cancelled
        ↓
Admin dashboard reflects cancellation
```

---

# 🏆 Project Highlights

### 🤖 Artificial Intelligence

AI-powered hotel receptionist capable of natural language interaction.

### 💬 Conversational Booking

Customers can complete hotel reservations through conversation.

### 🗄️ Real Database Operations

Booking operations are connected to actual backend/database functionality.

### 🔄 Complete Booking Lifecycle

Create → Confirm → Modify → Recalculate → Cancel.

### 👨‍💼 Professional Admin Dashboard

Hotel staff can monitor bookings, rooms, customers and hotel statistics.

### 👥 Guest Management

Adults and children are maintained as part of booking information.

### 💰 Dynamic Pricing

Booking totals are calculated based on room price and stay duration.

### 🌍 Multilingual Interaction

The AI can communicate in multiple languages.

### 🎙️ Voice AI

Voice-based hotel reception is integrated into the platform and is currently being refined for production-level reliability.

### ☁️ Cloud Deployment

The application is deployed using Railway.

---

# 📚 Learning Outcomes

This project demonstrates practical implementation of:

- Full-stack application development
- REST API development
- FastAPI
- SQLAlchemy
- Database design
- CRUD operations
- AI API integration
- Conversational AI
- Prompt-based AI interaction
- Booking management
- Dynamic price calculation
- Admin dashboard development
- Voice AI integration
- Frontend/backend integration
- Production deployment
- Environment variable management
- GitHub-based development

---

# 👨‍💻 Author

**Rahul**

### AI-Powered Hotel Management System

Built as a full-stack AI application combining hotel management with conversational and voice AI.

---

## ⭐ Core Concept

> **An AI receptionist that can actually interact with a hotel's booking system.**
