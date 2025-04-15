import pdfplumber
import httpx
from util.app_config import config
from datetime import datetime


async def process_cv_async(file_path) -> str:
    try:
        # Read PDF content
        with pdfplumber.open(file_path) as pdf:
            docs_content = "\n\n".join(page.extract_text() for page in pdf.pages)

        api_key = config.OPEN_ROUTER_KEY

        current_date = datetime.now()
        prompt = f"""You are a precise CV information extraction specialist. Extract the following information from the provided CV and structure it exactly into the specified JSON format. Return only the JSON object without any additional text or explanations.

        The JSON structure must be EXACTLY as follows:
        {{
        "first_name": "First Name",
        "last_name": "Last Name",
        "email": "Email",
        "phone_number": "Phone Number",
        "address": {{
            "street": "Street Address",
            "country": "Country"
        }},
        "date_of_birth": "Date of Birth (YYYY-MM-DD)",
        "years_of_experience": "Total Years of Experience (calculated as of {current_date.strftime('%B %Y')}, the way you calculate it is for each job experience you do end date minus start date which gives you a duration then you sum all the durations)",
        "job_title": "Current Job Title",
        "work_experience": [
            {{
            "title": "Job Title",
            "company": "Company Name",
            "start_date": "Start Date (YYYY-MM)",
            "end_date": "End Date (YYYY-MM or 'Present')",
            "location": "Location"
            }}
        ],
        "education": [
            {{
            "degree": "Degree",
            "major": "Major",
            "school": "School Name",
            "graduation_date": "Graduation Date (YYYY)"
            }}
        ],
        "skills": {{
            "general_skills": ["List of general skills"],
            "technical_skills": ["List of technical skills"],
            "languages": [
            {{
                "language": "Language Name",
                "level": "Proficiency Level"
            }}
            ]
        }},
        "certifications": [
            {{
            "certifier": "Certifier Name",
            "certification_name": "Certification Name"
            }}
        ]
        }}

        Important extraction guidelines:
        1. Follow the exact JSON schema structure provided above.
        2. For years_of_experience: Calculate precisely by summing the duration of all work experiences (end_date - start_date) through {current_date.strftime('%B %Y')}. For current positions, use {current_date.strftime('%B %Y')} as the end date.
        3. Extract dates consistently: YYYY-MM for work experience dates, YYYY for graduation dates, and YYYY-MM-DD for date of birth.
        4. Use "null" (without quotes) for any information that cannot be found in the CV.
        5. For work_experience, education, skills, and certifications, include all entries found in the CV.
        6. For current positions, use "Present" as the end_date value.
        7. Ensure all fields are properly populated with the correct information types.
        8. Do not add explanations, notes or any text outside the JSON structure.
        9. Carefully check the JSON formatting to ensure it is valid and properly nested.

        CV content:
        {docs_content}
        """

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "google/gemini-2.0-flash-001",
                    "messages": [{"role": "user", "content": prompt}],
                },
            )

            if response.status_code == 200:
                data = response.json()
                content = (
                    data.get("choices", [{}])[0].get("message", {}).get("content", "")
                )
                return content
            else:
                raise Exception(
                    f"API request failed with status code: {response.status_code}"
                )

    except Exception as e:
        raise Exception(f"Error processing CV: {str(e)}")
