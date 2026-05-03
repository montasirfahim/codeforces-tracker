from django.db import models

class StudentList(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Student(models.Model):
    student_list = models.ForeignKey(StudentList, on_delete=models.CASCADE, related_name='students')
    student_id = models.CharField(max_length=50, blank=True, null=True)
    name = models.CharField(max_length=255)
    handle = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.handle})"
