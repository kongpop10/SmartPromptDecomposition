import streamlit as st
from litellm import completion
from typing import List, Tuple
import json
import re

# Initialize session state variables
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'enable_prompt_splitting' not in st.session_state:
    st.session_state.enable_prompt_splitting = False
if 'model' not in st.session_state:
    st.session_state.model = "gpt-4o-mini"

def get_ai_response(prompt: str, model: str = "gpt-4o-mini") -> str:
    """Get response from AI model using liteLLM."""
    try:
        response = completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

def ai_prompt_decomposition(complex_prompt: str) -> List[str]:
    """Use AI to break down a complex prompt into smaller, logically connected prompts."""
    decomposition_prompt = f"""
    Break down this complex query into smaller, logically connected sub-queries. Consider:
    1. Dependencies between questions
    2. Context needed for each sub-query
    3. Logical flow of information
    
    Complex query: "{complex_prompt}"
    
    Return ONLY a JSON array of strings, where each string is a sub-query. Format:
    ["sub-query 1", "sub-query 2", ...]
    
    The sub-queries should build upon each other naturally and maintain context.
    """
    
    try:
        response = completion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": decomposition_prompt}],
            max_tokens=500
        )
        
        # Extract JSON array from response
        response_text = response.choices[0].message.content
        # Find the JSON array in the response (it might have additional text)
        start_idx = response_text.find('[')
        end_idx = response_text.rfind(']') + 1
        if start_idx != -1 and end_idx != -1:
            json_str = response_text[start_idx:end_idx]
            sub_prompts = json.loads(json_str)
            return sub_prompts if isinstance(sub_prompts, list) else []
        return [complex_prompt]
    except Exception as e:
        st.error(f"Error in prompt decomposition: {str(e)}")
        return [complex_prompt]

def process_prompt_chain(prompts: List[str]) -> List[Tuple[str, str]]:
    """Process a chain of prompts and get AI responses with context awareness."""
    responses = []
    context = ""
    
    for i, prompt in enumerate(prompts):
        # Create a context-aware prompt that includes previous interactions
        if context:
            context_prompt = f"""
            Given this context from previous responses: 
            {context}
            
            Please address this follow-up question while considering the above context:
            {prompt}
            """
        else:
            context_prompt = prompt
            
        response = get_ai_response(context_prompt)
        responses.append((prompt, response))
        
        # Update context with the latest response
        context += f"\nQ: {prompt}\nA: {response}\n"
    
    return responses

# Streamlit UI
st.title("AI Chat Assistant with Smart Prompt Decomposition")

# Add a switch for prompt splitting
st.sidebar.title("Settings")
enable_splitting = st.sidebar.toggle("Enable Smart Prompt Splitting", value=st.session_state.enable_prompt_splitting)
st.session_state.enable_prompt_splitting = enable_splitting

# Add model selection
selected_model = st.sidebar.text_input("AI Model", value=st.session_state.model)
st.session_state.model = selected_model

if enable_splitting:
    st.sidebar.info("Smart prompt splitting is enabled. Complex questions will be broken down and answered step by step.")

def format_message_content(content: str) -> None:
    """Format and display message content with proper rendering of Markdown, LaTeX, and code blocks."""
    # Split content by code blocks
    parts = re.split(r'(```[\w]*\n[\s\S]*?```)', content)
    
    for part in parts:
        if part.strip():
            if part.startswith('```') and part.endswith('```'):
                # Handle code blocks
                lines = part.split('\n')
                lang = lines[0][3:].strip()  # Get language if specified
                code = '\n'.join(lines[1:-1])  # Remove first and last lines (```) and join
                # Enhanced code block display with line numbers and wrap options
                st.code(
                    body=code,
                    language=lang if lang else "python",
                    line_numbers=True,
                    wrap_lines=True
                )
            else:
                # Handle LaTeX blocks (both inline and display)
                # First, convert bracketed equations to display LaTeX format
                part = re.sub(r'\[(.*?)\]', lambda m: f"\n$${{\n{m.group(1)}\n}}$$\n", part)
                
                # Then handle existing LaTeX blocks
                latex_parts = re.split(r'(\$\$[\s\S]*?\$\$|\$[^\$\n]*\$)', part)
                for latex_part in latex_parts:
                    if latex_part.strip():
                        if latex_part.startswith('$$') and latex_part.endswith('$$'):
                            # Display LaTeX
                            st.latex(latex_part[2:-2].strip())
                        elif latex_part.startswith('$') and latex_part.endswith('$'):
                            # Inline LaTeX - wrap in markdown
                            st.markdown(latex_part)
                        else:
                            # Regular markdown
                            st.markdown(latex_part)

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        format_message_content(message["content"])

# Chat input
if prompt := st.chat_input("What would you like to know?"):
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Process the prompt based on splitting setting
    if st.session_state.enable_prompt_splitting:
        with st.spinner("Analyzing your question..."):
            sub_prompts = ai_prompt_decomposition(prompt)
        
        if len(sub_prompts) > 1:
            st.info(f"I'll break this down into {len(sub_prompts)} parts to provide a more thorough response.")
            
            # Process and display each sub-prompt immediately
            context = ""
            for i, sub_prompt in enumerate(sub_prompts, 1):
                # Create a context-aware prompt
                if context:
                    context_prompt = f"""
                    Given this context from previous responses: 
                    {context}
                    
                    Please address this follow-up question while considering the above context:
                    {sub_prompt}
                    """
                else:
                    context_prompt = sub_prompt
                
                # Get and display the response immediately
                response = get_ai_response(context_prompt)
                with st.chat_message("assistant"):
                    st.markdown(f"**Part {i}**: *{sub_prompt}*\n\n{response}")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"**Part {i}**: {sub_prompt}\n\n{response}"
                })
                
                # Update context for the next sub-prompt
                context += f"\nQ: {sub_prompt}\nA: {response}\n"
        else:
            # Handle single prompt case
            response = get_ai_response(prompt, model=st.session_state.model)
            with st.chat_message("assistant"):
                st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
    else:
        # Normal chat mode
        response = get_ai_response(prompt, model=st.session_state.model)
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

