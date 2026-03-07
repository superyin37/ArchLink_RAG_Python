async def load_xlsx(file_path: str) -> str:
    """Load XLSX file as QA pairs or table text."""
    try:
        import openpyxl
    except ImportError:
        raise ImportError("openpyxl is required for XLSX loading")

    wb = openpyxl.load_workbook(file_path, read_only=True)
    parts = []

    for sheet in wb.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue

        # Get headers from first row
        headers = [str(cell) if cell is not None else "" for cell in rows[0]]

        for row in rows[1:]:
            row_values = [str(cell) if cell is not None else "" for cell in row]
            if any(v.strip() for v in row_values):
                # Format as Q&A if 2-column, otherwise as key-value pairs
                if len(headers) == 2:
                    parts.append(f"Q: {row_values[0]}\nA: {row_values[1]}")
                else:
                    row_text = " | ".join(
                        f"{h}: {v}" for h, v in zip(headers, row_values) if v.strip()
                    )
                    parts.append(row_text)

    wb.close()
    return "\n\n".join(parts)
