from autogen.agentchat.user_proxy_agent import UserProxyAgent
from autogen.agentchat.assistant_agent import AssistantAgent
from autogen.agentchat.groupchat import (GroupChat, GroupChatManager)
from autogen.agentchat.contrib.gpt_assistant_agent import GPTAssistantAgent

from fastapi import FastAPI # Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from pydantic import BaseModel


import openai
import pandas as pd
import os

from dotenv import load_dotenv, find_dotenv

_ = load_dotenv(find_dotenv())
api_key =  os.getenv("OPENAI_API_KEY")

app = FastAPI()

COMPLETION_PROMPT = "If everything looks good, respond with APPROVED"
USER_PROXY_PROMPT = (
    "A human admin. Interact with the Product Manager to discuss the plan. Plan execution needs to be approved by this admin." + COMPLETION_PROMPT
)

DATA_ENGINEER_PROMPT = ("""
            You are a skilled Data Engineer tasked with leveraging your expertise to tackle a range of data engineering challenges. 
            Your responsibilities include designing and optimizing database schemas, building efficient ETL processes, and implementing data warehousing solutions. 
            Additionally, you are expected to work with big data technologies, ensure data quality and governance, and provide clear documentation 
            for your code and data workflows. You also need to give clear analysis of data and reasoning behind your actions"""
)

SR_DATA_ANALYST_PROMPT = (
    "Sr Data Analyst. You follow an approved plan. You run the SQL query generate the response and send it to the Product Manager for final review." + COMPLETION_PROMPT
)

def is_termination_msg(content):
    have_content =  content.get("content", None) is not None
    if have_content and "APPROVED" in content["content"]:
        return True
    return False


class Context(BaseModel):
    question: str

class KnowledgeEngine:
    def __init__(self):
        self.client = openai.OpenAI(api_key=api_key)
        # df = pd.read_csv("synthetic_data_knowledge_base.csv")
        # df = df.head(100)
        # df.to_csv("synthetic_data_knowledge_base_sampled.csv", index=False)
        # self.file = self.client.files.create(
        #     file=open('synthetic_data_knowledge_base_sampled.csv', "rb"),
        #     purpose='assistants'
        # )

        self.config_list_gpt4 = [
            {
                'model': 'gpt-4',
                'api_key': api_key,
            },
        ]

        self.gpt4_config = {
            "seed": 42,  # change the seed for different trials
            "temperature": 0,
            "config_list": self.config_list_gpt4,
            "timeout": 120,
        }
    
    def engineer(self):
        engineer_assistant = AssistantAgent(
            name="Engineer",
            human_input_mode="NEVER",
            code_execution_config=False,
            system_message=DATA_ENGINEER_PROMPT,
            is_termination_msg=is_termination_msg,
            llm_config=self.gpt4_config,  # configuration for autogen's enhanced inference API which is compatible with OpenAI API
        )

        # engineer_assistant = self.client.beta.assistants.create(
        #     name="Data Engineer",
        #     instructions="""
            # You are a skilled Data Engineer tasked with leveraging your expertise to tackle a range of data engineering challenges. 
            # Your responsibilities include designing and optimizing database schemas, building efficient ETL processes, and implementing data warehousing solutions. 
            # Additionally, you are expected to work with big data technologies, ensure data quality and governance, and provide clear documentation 
            # for your code and data workflows. You also need to give clear analysis of data and reasoning behind your actions.
        #     """,
        #     model="gpt-4",
        #     tools = [ { "type": "code_interpreter" } ],
        #     file_ids=[self.file.id]
        # )
        return engineer_assistant

    def analyst(self):
        analyst_assistant = self.client.beta.assistants.create(
            name="Business Analyst",
            instructions="""
            You embody the role of a dynamic Business Analyst with a sharp focus on extracting meaningful insights from data. 
            Your mission is to provide comprehensive analyses and actionable recommendations to drive informed business decisions. 
            Leverage your expertise in data interpretation, statistical analysis, and business acumen to unravel patterns, trends, and key performance indicators. 
            Tailor your responses to address queries related to market trends, financial performance, and strategic planning. 
            Prioritize clarity and conciseness in your insights, ensuring your analyses empower stakeholders to make well-informed choices. 
            """,
            model="gpt-4",
            tools = [ { "type": "retrieval" } ],
            file_ids=[self.file.id]
        )
        return analyst_assistant
    
    def ask_agent(self, assistant, prompt):
        # assitant_llm_config = {
        #     "assistant_id": assistant.id,
        #     'api_key': api_key,
        # }

        # my_assistant = GPTAssistantAgent(
        #     instructions="""
        #     You are a skilled Data Engineer tasked with leveraging your expertise to tackle a range of data engineering challenges. 
        #     Your responsibilities include designing and optimizing database schemas, building efficient ETL processes, and implementing data warehousing solutions. 
        #     Additionally, you are expected to work with big data technologies, ensure data quality and governance, and provide clear documentation 
        #     for your code and data workflows. You also need to give clear analysis of data and reasoning behind your actions.
        #     If everything looks good, respond with APPROVED.
        #     """,  
        #     is_termination_msg=is_termination_msg,
        #     llm_config=assitant_llm_config
        # )

        user_proxy = UserProxyAgent(
            name="Client",
            code_execution_config={
                "work_dir" : "coding",
            },
            human_input_mode="NEVER",
            is_termination_msg=is_termination_msg,
            system_message=USER_PROXY_PROMPT,
            llm_config=self.gpt4_config
        )

        # groupchat = GroupChat(agents=[user_proxy, engineer, analyst], messages=[], max_round=10)
        # manager = GroupChatManager(groupchat=groupchat, llm_config=gpt4_config)

        user_proxy.initiate_chat(assistant, message=prompt)
        
        chat_messages =  user_proxy.chat_messages   
        # print(chat_messages)
        return chat_messages


my_agent = KnowledgeEngine()

@app.get("/")
def read_root():
    return {"message": "Hello, Autogen!"}


@app.post('/agent/ask')
async def ask_agent(input: Context):
    answer = my_agent.ask_agent(my_agent.engineer(), input.question)
    # Convert the answer to a simplified JSON-serializable format, excluding GPTAssistantAgent
    simplified_answer = {
        'agent.name': [{'content': msg['content'], 'role': msg['role']} for msg in messages]
        for agent, messages in answer.items()
    }

    return JSONResponse(content={'answer': simplified_answer})
   
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
