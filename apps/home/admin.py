from django.contrib import admin

from .models import Project, ProjectVersion, Recommendation, SimilarityCheck, SimilarityMatch

admin.site.register([Project, ProjectVersion, SimilarityCheck, SimilarityMatch, Recommendation])
