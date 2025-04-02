




import json
from typing import Tuple
from fastapi import APIRouter
from schema.chat import CreateTempSessionRequest, SendMessageRequest, CreateTempSessionResponse
from db.models import ChatMessages, User, ChatSession, Candidate, TempChatSession
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from fastapi import Depends
from auth.Oth2 import get_current_user
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from util.app_config import config
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/chat")

@router.post("/temp_session")
async def create_temp_session(message_data: CreateTempSessionRequest, dbps: Tuple[User, AsyncSession] = Depends(get_current_user)):
    user, db = dbps
    chat_session = TempChatSession(
        id = str(uuid4()),
        user_id = user.id,
        candidates = message_data.candidates
    )
    db.add(chat_session)
    await db.commit()
    return CreateTempSessionResponse(session_id=chat_session.id)


@router.post("/send")
async def send_message(message_data: SendMessageRequest, dbps: Tuple[User, AsyncSession] = Depends(get_current_user)):
    user, db = dbps

    session_query = await db.execute(select(ChatSession).where(ChatSession.id == message_data.session_id))
    chat_session = session_query.scalar_one_or_none()

    if chat_session is None:
        temp_session_query = await db.execute(select(TempChatSession).where(TempChatSession.id == message_data.session_id))
        temp_session = temp_session_query.scalar_one_or_none()
        if temp_session is None:
            raise Exception("Session not found")
        if temp_session.user_id != user.id:
            raise Exception("Unauthorized")
        chat_session = ChatSession(
            id = temp_session.id,
            user_id = user.id,
            candidates = temp_session.candidates
        )
        db.add(chat_session)
        await db.commit()

        chat_history = []
    else:
        if chat_session.user_id != user.id:
            raise Exception("Unauthorized")
        chat_history_q = await db.execute(select(ChatMessages).where(ChatMessages.chat_session_id == chat_session.id))
        chat_history_obj = chat_history_q.scalars().all()
        candidates_data= ["you will find it in chat history"]
        chat_history = []
        for chat in chat_history_obj:
            chat_history.append({
                "id": chat.id,
                "sender": chat.sender,
                "content": chat.content
            })
    
    

    candidates_data_q = await db.execute(
            select(Candidate)
            .options(joinedload(Candidate.resume))  # This eagerly loads the resume relationship
            .where(Candidate.id.in_(chat_session.candidates))
        )
    candidates_objs = candidates_data_q.scalars().all()
    candidates_data = []
    for candidate in candidates_objs:
            candidates_data.append({
                "id": candidate.id,
                "first_name": candidate.first_name,
                "last_name": candidate.last_name,
                "email": candidate.email,
                "phone_number": candidate.phone_number,
                "address": candidate.address,
                "date_of_birth": candidate.date_of_birth,
                "years_of_experience": candidate.years_of_experience,
                "job_title": candidate.job_title,
                "work_experience": candidate.work_experience,
                "education": candidate.education,
                "skills": candidate.skills,
                "certifications": candidate.certifications,
                "resume_link" : candidate.resume.file_path
            })


    
    system_instruction ="""
    You are an AI assistant helping a recruiter analyze candidate data and make hiring decisions.
    Your task is to provide objective analysis based on the candidate information provided.
    
    When comparing candidates:
    - Focus on relevant skills and experience
    - Highlight strengths and potential areas of concern
    - Avoid bias based on personal details
    - Respond directly to the recruiter's questions
    
    Format your responses in clear, professional language suitable for recruitment professionals.
    """

    print (candidates_data)
    print("=====================================")
    print (chat_history)


    prompt = f"""
    {system_instruction}
    
    CANDIDATE INFORMATION:
    {candidates_data}
    
    PREVIOUS CONVERSATION:
    {chat_history}
    
    RECRUITER'S QUESTION:
    {message_data.message}
    """
    
    model = OpenAIModel(
        'mistralai/mistral-small-3.1-24b-instruct',
        provider=OpenAIProvider(
            base_url='https://openrouter.ai/api/v1',
            api_key= config.OPEN_ROUTER_KEY,
        ),
    )

    agent = Agent(model=model)

    # Save the user message to the database
    user_message = ChatMessages(
        chat_session_id=chat_session.id,
        sender="user",
        content=message_data.message
    )
    db.add(user_message)
    await db.commit()

# Create a new assistant message but don't commit it yet
    ai_message = ChatMessages(
        chat_session_id=chat_session.id,
        sender="assistant",
        content=""  # Will be updated before committing
    )
    db.add(ai_message)
    # Get the ID without committing
    await db.flush()
    message_id = ai_message.id
    await db.commit()  # Commit the empty message first

    async def event_generator():
        full_response = ""
        error_occurred = False
        error_message = ""
        
        try:
            async with agent.run_stream(prompt) as result:
                async for message in result.stream_text(delta=True):
                    if message:  # Only add non-empty deltas
                        full_response += message
                        yield {
                            "event": "message",
                            "data": json.dumps({
                                "delta": message,
                                "message_id": str(message_id),
                                "chat_id": str(chat_session.id)
                            })
                        }
        except Exception as e:
            error_occurred = True
            error_message = str(e)
            import traceback
            print(f"Error during streaming: {str(e)}")
            traceback.print_exc()
            yield {
                "event": "error",
                "data": json.dumps({
                    "error": str(e),
                    "message_id": str(message_id),
                    "chat_id": str(chat_session.id)
                })
            }
        finally:
            # Always update the message in the database, even if there was an error
            try:
                # Create a new session for the update to avoid transaction issues
                async with AsyncSession(db.bind) as update_session:
                    # If we got a response, use it; otherwise use error message or default text
                    final_content = full_response
                    if not final_content and error_occurred:
                        final_content = f"Error processing request: {error_message}"
                    elif not final_content:
                        final_content = "No response received from the model. Please try again."
                    
                    # Update the message with the complete content
                    await update_session.execute(
                        update(ChatMessages)
                        .where(ChatMessages.id == message_id)
                        .values(content=final_content)
                    )
                    await update_session.commit()
                    print(f"Database updated with content length: {len(final_content)}")
            except Exception as db_error:
                print(f"Error updating database: {str(db_error)}")
                import traceback
                traceback.print_exc()
            
            # Signal the end of the stream
            yield {
                "event": "done",
                "data": json.dumps({
                    "message_id": str(message_id),
                    "chat_id": str(chat_session.id)
                })
            }

    return EventSourceResponse(event_generator())
   
    

    


