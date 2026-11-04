from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Room, RoomMember, Match, Prediction, UserProfile

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'total_points', 'exact_hits', 'winner_hits',
            'diff_hits', 'streak_bonuses', 'early_bonuses', 'current_streak',
            'max_streak', 'updated_at'
        ]


class MatchSerializer(serializers.ModelSerializer):
    is_finished = serializers.BooleanField(read_only=True)
    outcome = serializers.CharField(read_only=True)

    class Meta:
        model = Match
        fields = [
            'id', 'team_home', 'team_away', 'home_flag', 'away_flag',
            'stage', 'group_name', 'stadium', 'match_date', 'status',
            'home_score', 'away_score', 'is_finished', 'outcome'
        ]


class PredictionSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    match_detail = MatchSerializer(source='match', read_only=True)

    class Meta:
        model = Prediction
        fields = [
            'id', 'user', 'match', 'match_detail', 'home_score_pred', 'away_score_pred',
            'created_at', 'updated_at', 'exact_score_points', 'winner_points',
            'diff_points', 'streak_bonus_points', 'early_bonus_points',
            'total_points', 'is_evaluated', 'rule_breakdown'
        ]
        read_only_fields = [
            'exact_score_points', 'winner_points', 'diff_points',
            'streak_bonus_points', 'early_bonus_points', 'total_points',
            'is_evaluated', 'rule_breakdown'
        ]


class RoomMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = RoomMember
        fields = ['id', 'user', 'joined_at']


class RoomSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    memberships = RoomMemberSerializer(many=True, read_only=True)

    class Meta:
        model = Room
        fields = ['id', 'name', 'description', 'code', 'created_by', 'created_at', 'member_count', 'memberships']
        read_only_fields = ['code', 'created_at', 'member_count']
