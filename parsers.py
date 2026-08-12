import re
import json

def parse_llm_response(model_output: str) -> dict:
    """
    Parses output from Qwen3-Coder. Captures and fixes leaked 
    XML tool call tags before falling back to JSON.
    """
    # Force string type and strip exterior whitespace
    text = str(model_output).strip()
    
    # Check if Qwen's XML format is present
    if "</function>" in text or "</tool_call>" in text:
        # Match the function name and internal parameter block
        func_match = re.search(r"<function=(.*?)>(.*?)</function>", text, re.DOTALL)
        if func_match:
            func_name = func_match.group(1).strip()
            params_raw = func_match.group(2)
            
            # Find all key-value parameter pairs
            param_pairs = re.findall(r"<parameter=(.*?)>(.*?)</parameter>", params_raw, re.DOTALL)
            arguments = {k.strip(): v.strip() for k, v in param_pairs}
            
            return {
                "status": "success",
                "type": "xml_tool_call",
                "name": func_name,
                "arguments": arguments
            }
            
    # Fallback to standard JSON parsing if no XML tags are found
    try:
        parsed_json = json.loads(text)
        return {
            "status": "success",
            "type": "json",
            "data": parsed_json
        }
    except json.JSONDecodeError:
        # Return the raw text if both formats fail
        return {
            "status": "failed",
            "type": "raw_text",
            "data": text
        }
