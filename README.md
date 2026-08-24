# rasa-pro-restaurant-assistant

Python Version: 3.11.12

This repository is for a chatbot on RASA Pro that assists a Spanish restaurant mainly for reservations, but also for menu inquiries and other FAQs

Spanish Restaurant Reservation Assistant built with Rasa Pro and CALM

A conversational assistant that handles restaurant information and table reservations in Spanish.
The assistant uses Rasa Pro flows and custom Python actions to collect reservation information, validate user input, check table availability,
and suggest alternative reservation times when the requested slot is unavailable.

Features
- Spanish-language conversational interface
- Restaurant opening-hours and menu queries
- Multi-step reservation flow
- Slot collection for date, time, party size, name and phone
- Input validation
- Custom Python actions
- Availability checking using structured restaurant data
- Alternative time suggestions
- Reservation confirmation and cancellation
- Chitchat and fallback handling

## Example Conversations

### Restaurant reservation

<img width="975" height="348" alt="image" src="https://github.com/user-attachments/assets/8f88b063-d9e3-468f-b819-92aa1212a99b" />

### Alternative reservation

<img width="1079" height="470" alt="image" src="https://github.com/user-attachments/assets/3e268ebe-b961-489c-b6ef-f5777b8d3ace" />
