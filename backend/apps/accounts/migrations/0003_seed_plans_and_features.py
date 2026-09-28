from django.db import migrations

FEATURES = [
    ("stats", "Detailed team and player stats, kill feed"),
    ("rotations.view", "Rotation maps, drop spots, annotations, shared views"),
    ("zone_analysis", "Safe zone analysis and heatmaps"),
    ("scouting", "Scouting pages for other teams"),
    ("head_to_head", "Compare two teams"),
    ("reports", "PDF reports"),
    ("assistant", "AI assistant (phase 2)"),
]


def seed(apps, schema_editor):
    Feature = apps.get_model("accounts", "Feature")
    Plan = apps.get_model("accounts", "Plan")
    Team = apps.get_model("league", "Team")
    features = [
        Feature.objects.update_or_create(code=code, defaults={"description": text})[0]
        for code, text in FEATURES
    ]
    plan, _ = Plan.objects.get_or_create(code="league_team", defaults={"name": "League team"})
    plan.features.add(*features)
    Team.objects.filter(is_league_member=True, plan__isnull=True).update(plan=plan)


def unseed(apps, schema_editor):
    apps.get_model("league", "Team").objects.filter(plan__code="league_team").update(plan=None)
    apps.get_model("accounts", "Plan").objects.filter(code="league_team").delete()
    apps.get_model("accounts", "Feature").objects.filter(code__in=[c for c, _ in FEATURES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_feature_invite_plan_staffprofile_membership_and_more"),
        ("league", "0003_player_user_team_plan_rosterentry"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
