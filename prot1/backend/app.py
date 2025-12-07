from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from tree_sitter import Parser
import tree_sitter_languages as tsl

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    code: str
    language: str  # "c", "python", "javascript", etc.
    targets: list[str] | None = None  # 抽出したい概念。空なら全件

def get_parser(lang: str) -> Parser:
    try:
        language = tsl.get_language(lang)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{lang}': {e}")
    parser = Parser()
    parser.set_language(language)
    return parser

@app.get("/health")
def health():
    return {"status": "ok", "languages": tsl.get_language_names()}

@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    parser = get_parser(req.language)
    try:
        tree = parser.parse(req.code.encode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse error: {e}")

    source = req.code
    root = tree.root_node

    concepts = {
        "keywords": set(),
        "operators": set(),
        "control_structures": set(),
        "function_calls": set(),
        "identifiers": set(),
        "literals": set(),
    }

    def text(node):
        return source[node.start_byte:node.end_byte]

    def walk(node):
        nt = node.type

        if nt in ("if_statement", "for_statement", "while_statement", "switch_statement"):
            concepts["control_structures"].add(nt)

        if nt in ("call_expression", "function_call"):
            for child in node.children:
                if child.type == "identifier":
                    concepts["function_calls"].add(text(child))

        op_node = node.child_by_field_name("operator")
        if op_node:
            concepts["operators"].add(text(op_node))

        if nt == "identifier":
            concepts["identifiers"].add(text(node))
        if nt in ("number_literal", "string_literal", "char_literal"):
            concepts["literals"].add(text(node))

        if nt in ("for", "if", "else", "return", "while", "switch", "case", "default", "break", "continue"):
            concepts["keywords"].add(nt)

        for child in node.children:
            walk(child)

    walk(root)
    result = {k: sorted(v) for k, v in concepts.items()}

    if req.targets:
        targets_set = set(req.targets)
        result = {k: [x for x in arr if x in targets_set] for k, arr in result.items()}

    return result
