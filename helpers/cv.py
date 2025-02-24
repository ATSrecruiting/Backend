import pdfplumber
import httpx


async def process_cv_async(file_path):
    try:
        # Read PDF content
        with pdfplumber.open(file_path) as pdf:
            docs_content = "\n\n".join(page.extract_text() for page in pdf.pages)

        api_key = (
            "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"
        )
        prompt = f"""You will be given a CV. Extract the following information and structure it into a JSON object. Do not output any additional text or explanations—only the JSON object. If any information is missing or cannot be found, use `null` as the value.

            Here is the structure of the JSON object you must return:
            ```json
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
            "years_of_experience": "Total Years of Experience (calculated as of January 2025, the way you calculate it is for each job experience you do end date minus start date which gives you a duration the you summ all the durations)",
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
            "education": {{
                "degree": "Degree",
                "major": "Major",
                "school": "School Name",
                "graduation_date": "Graduation Date (YYYY)"
            }},
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
            Now, here is the CV:
            {docs_content}

            Return only the JSON object as described above. Do not include any additional text or explanations.

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
