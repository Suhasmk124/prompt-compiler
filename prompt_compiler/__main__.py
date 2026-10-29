import argparse
from pathlib import Path
from .schema import Workflow
from .executor import execute


def main():
    parser = argparse.ArgumentParser(description='Execute a saved Prompt Compiler workflow locally.')
    parser.add_argument('workflow', type=Path)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('outputs'))
    args = parser.parse_args()
    workflow = Workflow.model_validate_json(args.workflow.read_text(encoding='utf-8-sig'))
    files = {p.name: p.read_bytes() for p in args.inputs.iterdir() if p.is_file()}
    run = execute(workflow, files)
    if run.error:
        parser.exit(1, run.error + '\n')
    args.output.mkdir(parents=True, exist_ok=True)
    for name, content in run.artifacts.items():
        target = args.output / name
        if target.exists():
            parser.exit(1, f'Refusing to overwrite existing output: {target}\n')
    for name, content in run.artifacts.items():
        target = args.output / name
        target.write_bytes(content)
        print(f'Created {target}')


if __name__ == '__main__':
    main()
