from django.contrib import admin
from .models import Room, RoomMember, Match, Prediction, UserProfile
from .scoring import recalculate_all_scores

@admin.action(description="Recalcular puntuaciones para partidos seleccionados")
def recalculate_selected(modeladmin, request, queryset):
    recalculate_all_scores()

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'team_home', 'home_score', 'away_score', 'team_away', 'status', 'stage', 'match_date')
    list_filter = ('status', 'stage', 'group_name')
    search_fields = ('team_home', 'team_away', 'stadium')
    actions = [recalculate_selected]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.status == 'FINISHED':
            recalculate_all_scores()

@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'match', 'home_score_pred', 'away_score_pred', 'total_points', 'is_evaluated')
    list_filter = ('is_evaluated', 'match')
    search_fields = ('user__username', 'match__team_home', 'match__team_away')

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code', 'created_by', 'member_count', 'created_at')
    search_fields = ('name', 'code', 'created_by__username')

@admin.register(RoomMember)
class RoomMemberAdmin(admin.ModelAdmin):
    list_display = ('id', 'room', 'user', 'joined_at')
    list_filter = ('room',)
    search_fields = ('user__username', 'room__name')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_points', 'exact_hits', 'winner_hits', 'diff_hits', 'current_streak', 'max_streak')
    search_fields = ('user__username',)
    ordering = ('-total_points',)
