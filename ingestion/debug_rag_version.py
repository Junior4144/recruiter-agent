from vertexai import rag
import google.cloud.aiplatform as aiplatform
import inspect

print("google-cloud-aiplatform version:", aiplatform.__version__)
print()
print("import_files signature:")
print(inspect.signature(rag.import_files))