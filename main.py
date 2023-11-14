from modules.db import PostgreSQLDatabase
from modules import llm
import os
import dotenv
import argparse

from autogen import (
    AssistantAgent,
    UserProxyAgent,
    GroupChat,
    GroupChatManager,
    config_list_from_json,
    config_list_from_models,
)


dotenv.load_dotenv()

assert os.environ.get("DB_URL"), "postgres_connection_url not found in .env file"
assert os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY not found in.env file"

DB_URL = os.environ.get("DB_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

POSTGRES_TABLE_DEFINITIONS_CAP_REF =  "TABLE_DEFINITIONS"
RESPONSE_FORMAT_CAP_REF = "RESPONSE_FORMAT"
SQL_DELIMITER = "___________"

config_list = [
    {
        'model': 'gpt-4'
    }
]

llm_config={
    "use_cache": False,
    "request_timeout": 1000,
    "config_list": config_list_from_models(["gpt-4"]),
    "temperature": 0.00000001,
    "functions": [
        {
            "name": "run_sql",
            "description": "Run a SQL query against the postgres database",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL query to run",
                    }
                },
                "required": ["sql"],
            }
        }
    ]
}

def is_termination_msg(content):
    have_content =  content.get("content", None) is not None
    if have_content and "APPROVED" in content["content"]:
        return True
    return False

COMPLETION_PROMPT = "If everything looks good, respond with APPROVED"

USER_PROXY_PROMPT = (
    "A human admin. Interact with the Product Manager to discuss the plan. Plan execution needs to be approved by this admin." + COMPLETION_PROMPT
)

DATA_ENGINEER_PROMPT = (
    "A Data Engineer. You follow an approved plan. Generate the initial SQL based on the requirements provided. Send it to the Sr Data Analyst for review" + COMPLETION_PROMPT
)

SR_DATA_ANALYST_PROMPT = (
    "Sr Data Analyst. You follow an approved plan. You run the SQL query generate the response and send it to the Product Manager for final review." + COMPLETION_PROMPT
)

PRODUCT_MANAGER_PROMPT = (
    "Product Manager. Validate the response to makse sure it is correct" + COMPLETION_PROMPT
)



def main():
    # parse prompt param using arg parse
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", help="The prompt for the AI")
    args = parser.parse_args()

    if not args.prompt:
        print("Please provide a prompt")
        return

    prompt = f"Fulfill this database query: {args.prompt}."

    with PostgreSQLDatabase() as db:
        db.connect_with_url(DB_URL)

        function_map = {
            "run_sql": db.run_sql,
            "get_table_def": db.get_table_definition,
        }


        # table_definitions =  db.get_table_definitions_for_prompt()
        # table_definitions =  db.get_table_definitions_for_prompt()

        prompt = llm.add_cap_ref(
            prompt,
            f"understand the table context by listing all columns in the table",
            "",
            "",
        )

        # create an AssistantAgent named "assistant"
        data_engineer = AssistantAgent(
            name="Engineer",
            human_input_mode="NEVER",
            code_execution_config=False,
            system_message=DATA_ENGINEER_PROMPT,
            is_termination_msg=is_termination_msg,
            llm_config=llm_config,  # configuration for autogen's enhanced inference API which is compatible with OpenAI API
        )

        sr_data_analyst = AssistantAgent(
            name="Sr_Data_Analyst",
            human_input_mode="NEVER",
            code_execution_config=False,
            system_message=SR_DATA_ANALYST_PROMPT,
            is_termination_msg=is_termination_msg,
            llm_config=llm_config, 
            function_map=function_map# configuration for autogen's enhanced inference API which is compatible with OpenAI API
        )

        product_manager = AssistantAgent(
            name="Product_Manager",
            human_input_mode="NEVER",
            code_execution_config=False,
            system_message=PRODUCT_MANAGER_PROMPT,
            is_termination_msg=is_termination_msg,
            llm_config=llm_config,  # configuration for autogen's enhanced inference API which is compatible with OpenAI API
        )

        # create a UserProxyAgent instance named "user_proxy"
        user_proxy = UserProxyAgent(
            name="user_proxy",
            human_input_mode="NEVER",
            system_message=USER_PROXY_PROMPT,
            is_termination_msg=is_termination_msg,
            code_execution_config=False,
            llm_config=llm_config,
        )

        groupchat = GroupChat(
            agents=[user_proxy, data_engineer, sr_data_analyst, product_manager],
            messages=[],
            max_round=100,
        )

        manager = GroupChatManager(groupchat=groupchat, llm_config=llm_config)
        # the assistant receives a message from the user_proxy, which contains the task description
        user_proxy.initiate_chat(
            manager,
            clear_history=True,
            message=prompt,
        )

        

if __name__ == "__main__":
    main()