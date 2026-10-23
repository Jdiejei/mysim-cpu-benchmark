"""Exact-source executable entry point. No prose interpretation or generic fallback."""
import hashlib,importlib.util
from pathlib import Path

def execute_mesh_program(obj,recipe):
 program=recipe['executable_program'];root=Path(__file__).resolve().parent;p=(root/program['file']).resolve();assert p.is_relative_to(root/'mesh_programs'),'Invalid executable program path';assert hashlib.sha256(p.read_bytes()).hexdigest()==program['sha256'],'Executable procedure hash mismatch'
 spec=importlib.util.spec_from_file_location('mesh_program_'+recipe['procedure_id'],p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);assert module.SOURCE_ID==recipe['procedure_id'];return module.apply(obj,recipe)
