from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="Limes Axis API",
        description="Core API for the sovereign AI control plane for European operations.",
        version="0.0.0",
        license_info={
            "name": "Apache-2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        },
    )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "axis-api"}

    return app


app = create_app()
