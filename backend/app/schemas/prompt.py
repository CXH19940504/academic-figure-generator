from pydantic import BaseModel, ConfigDict, Field


class PromptGenerateRequest(BaseModel):
    document_id: str | None = None  # explicit document selection
    section_indices: list[int] = Field(default_factory=list, description="Section indices to generate prompts for")  # # None means all sections
    color_scheme: str = "okabe-ito"
    custom_colors: dict | None = None
    figure_types: list[str] | None = None
    user_request: str | None = None
    max_figures: int | None = None
    template_mode: bool = False


class PromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    document_id: str | None
    material_type: int | None
    figure_number: int
    title: str | None
    original_prompt: str | None
    edited_prompt: str | None
    active_prompt: str | None
    suggested_figure_type: str | None
    suggested_aspect_ratio: str | None
    source_sections: dict | list | None
    claude_model: str | None
    generation_status: str


class PromptUpdate(BaseModel):
    edited_prompt: str


class PromptStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    generation_status: str
