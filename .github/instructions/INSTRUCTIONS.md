# Instagram Fitness Community Chatbot

## Project Goal

Create a simple Instagram chatbot for a fitness community with two branches.

The chatbot must answer frequently asked questions and collect potential customer information.

## Business Information

Branches:

* Guadalupe
* Bosque Santa Anita

Program availability by branch:

* Guadalupe: HYROX, Full Training, Wellness, Running
* Bosque Santa Anita: HYROX, Full Training

Programs:

* HYROX
* Full Training
* Wellness
* Running

### Wellness Special Flow

Wellness should have its own visible button in the chatbot.

Rules:

* If the user selects or asks for Wellness, the chatbot should enter a Wellness-specific flow.
* If the user asks for prices in Wellness, send the same pricing image used for Guadalupe.
* If the user asks for location, branch, or where Wellness is available, respond with the same location as Guadalupe.
* If the user asks for schedules in Wellness, do not send the normal schedule text; instead send a WhatsApp link and tell the user to schedule their appointment.
* The WhatsApp number for Wellness can remain as a placeholder until it is replaced later in the config.

## Chatbot Personality

The chatbot should be:

* Friendly
* Professional
* Motivational
* Helpful
* Short and concise

Responses should feel natural and welcoming.

## Welcome Message

"¡Hola! 👋 Bienvenido a FULL.

Aquí entrenamos, sudamos y cumplimos objetivos... aunque prometemos que las burpees no son obligatorias en esta conversación 😄.

Estoy aquí para ayudarte con información sobre nuestras clases, horarios, costos, sucursales y clases muestra.

¿En qué puedo ayudarte hoy?"

## Frequently Asked Questions

### Location

User examples:

* Where are you located?
* What branches do you have?
* Where can I train?

Response:

"We currently have two locations:

📍 Guadalupe

📍 Bosque Santa Anita

Which location would you like more information about?"

### Schedules

User examples:

* What are your schedules?
* What classes do you have?
* When can I train?

Flow:

1. Ask which branch the user is interested in.
2. Send the corresponding schedule image.

Guadalupe:

* Send Guadalupe schedule image.

Bosque Santa Anita:

* Send Bosque Santa Anita schedule image.

### HYROX Information

User examples:

* What is HYROX?
* What does HYROX include?
* Tell me about HYROX

Response:

"HYROX is a functional fitness training program that combines endurance and strength-based exercises designed to improve overall performance, fitness, and conditioning."

### Membership Pricing

User examples:

* How much is the membership?
* What are the prices?
* Monthly fee?

Flow:

1. Ask which branch the user is interested in.
2. Send the corresponding pricing image.

Guadalupe:

* Send Guadalupe pricing image.

Bosque Santa Anita:

* Send Bosque Santa Anita pricing image.

### Trial Class

User examples:

* Can I try a class?
* Do you offer trial classes?
* Free trial?

Flow:

1. Ask which branch the user prefers.
2. Send the corresponding WhatsApp link.

Guadalupe:

* Send Guadalupe WhatsApp link.

Bosque Santa Anita:

* Send Bosque Santa Anita WhatsApp link.

## Lead Capture

Register the lead automatically as soon as the chatbot receives the first written message from the user.

Rules:

* Do not ask the user whether they want to register.
* Do not ask for full name, phone number, program, or branch just for lead capture.
* Use the Instagram username as the Name in the Excel file.
* Create the lead automatically on the first message.
* Update that same lead automatically when the user later provides a phone number, mentions a program, or mentions a branch.
* If the user writes their real name in phrases like "me llamo Juan Pérez" or "mi nombre es Juan Pérez", update the lead name with that value.
* Requests for pricing, schedules, trial class, or enrollment should also update the same lead if they reveal more data.
* If program or branch are not yet known, store "Sin especificar" in those fields.
* Phone Number can be saved empty if it was not provided by the user.
* The chatbot should not announce or ask for registration confirmation; registration happens in the background.
* The visible quick replies should not include a signup button.

Excel Columns:

* Date
* Name
* Phone Number
* Program
* Branch
* Source (Instagram)

## Human Handoff

If the chatbot cannot answer a question or the user requests assistance, provide the corresponding branch WhatsApp contact.

Response:

"Our team will be happy to assist you directly. Please contact the branch through WhatsApp."
