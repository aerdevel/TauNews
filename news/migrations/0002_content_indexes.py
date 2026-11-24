from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("news", "0001_initial")]

    operations = [
        migrations.AddIndex(
            model_name="article",
            index=models.Index(fields=["status", "published_at"], name="article_status_pub_idx"),
        ),
        migrations.AddIndex(
            model_name="article",
            index=models.Index(fields=["category", "status", "published_at"], name="article_cat_status_idx"),
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(fields=["article", "is_approved", "created_at"], name="comment_moderation_idx"),
        ),
    ]
