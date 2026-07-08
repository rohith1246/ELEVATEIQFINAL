import sys
import os
# Add backend folder to python search path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest
from unittest.mock import patch, MagicMock
from elevateiq_app import create_app


class EduTechTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    @patch('elevateiq_app.routes.edutech_routes.get_connection')
    def test_get_courses_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock active courses list
        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'title': 'Test Course',
                'level': 'Beginner',
                'duration': '10 weeks',
                'price': 15000.0,
                'old_price': 20000.0,
                'rating': 4.5,
                'icon': 'layers',
                'is_active': True
            }
        ]
        
        response = self.client.get('/api/edutech/courses')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test Course', response.data)

    @patch('elevateiq_app.routes.edutech_routes.get_connection')
    @patch('elevateiq_app.routes.edutech_routes.get_current_user')
    def test_enroll_in_course_success(self, mock_get_user, mock_get_conn):
        # Mock logged-in student user
        mock_get_user.return_value = {
            'id': 10,
            'name': 'Student User',
            'email': 'student@example.com',
            'role': 'candidate'
        }
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Course exists and is active, and student is not enrolled yet
        mock_cursor.fetchone.side_effect = [
            {'price': 15000.0, 'is_active': True}, # SELECT price, is_active FROM courses
            None, # SELECT id FROM course_enrollments
            (42,) # RETURNING id
        ]
        
        response = self.client.post('/api/edutech/enroll', json={'course_id': 1})
        self.assertEqual(response.status_code, 201)
        self.assertIn(b'Enrolled successfully', response.data)

    @patch('elevateiq_app.routes.edutech_routes.get_connection')
    @patch('elevateiq_app.auth.get_current_user')
    def test_create_course_forbidden_for_candidates(self, mock_get_user, mock_get_conn):
        # Candidate/student roles should be forbidden from creating courses
        mock_get_user.return_value = {
            'id': 10,
            'name': 'Student User',
            'email': 'student@example.com',
            'role': 'candidate'
        }
        
        response = self.client.post('/api/edutech/courses', json={
            'title': 'Hack Course',
            'level': 'Beginner',
            'duration': '5 weeks',
            'price': 100
        })
        self.assertEqual(response.status_code, 403) # Forbidden

    @patch('elevateiq_app.routes.edutech_routes.get_connection')
    @patch('elevateiq_app.auth.get_current_user')
    def test_create_course_success_for_admin(self, mock_get_user, mock_get_conn):
        # Admins can create courses
        mock_get_user.return_value = {
            'id': 1,
            'name': 'Admin User',
            'email': 'admin@example.com',
            'role': 'admin'
        }
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchone.return_value = {
            'id': 5,
            'title': 'New Admin Course',
            'level': 'Advanced',
            'duration': '12 weeks',
            'price': 30000.0,
            'old_price': None,
            'rating': 5.0,
            'icon': 'code',
            'created_at': None
        }
        
        response = self.client.post('/api/edutech/courses', json={
            'title': 'New Admin Course',
            'level': 'Advanced',
            'duration': '12 weeks',
            'price': 30000
        })
        self.assertEqual(response.status_code, 201)
        self.assertIn(b'New Admin Course', response.data)

    @patch('elevateiq_app.routes.edutech_routes.get_connection')
    @patch('elevateiq_app.routes.edutech_routes.get_current_user')
    @patch('elevateiq_app.auth.get_current_user')
    def test_get_enrollments_as_admin(self, mock_get_user_auth, mock_get_user_route, mock_get_conn):
        user_info = {
            'id': 1,
            'name': 'Admin User',
            'email': 'admin@elevateiq.com',
            'role': 'admin'
        }
        mock_get_user_auth.return_value = user_info
        mock_get_user_route.return_value = user_info
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'price_paid': 15000.0,
                'enrolled_at': None,
                'status': 'Active',
                'student_name': 'Student',
                'student_email': 'student@example.com',
                'course_title': 'Math'
            }
        ]
        
        response = self.client.get('/api/edutech/enrollments')
        self.assertEqual(response.status_code, 200)
        import json
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data[0]['price_paid'], 15000.0)

    @patch('elevateiq_app.routes.edutech_routes.get_connection')
    @patch('elevateiq_app.routes.edutech_routes.get_current_user')
    @patch('elevateiq_app.auth.get_current_user')
    def test_get_enrollments_as_employee(self, mock_get_user_auth, mock_get_user_route, mock_get_conn):
        user_info = {
            'id': 2,
            'name': 'Employee User',
            'email': 'employee@elevateiq.com',
            'role': 'employee'
        }
        mock_get_user_auth.return_value = user_info
        mock_get_user_route.return_value = user_info
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'price_paid': 15000.0,
                'enrolled_at': None,
                'status': 'Active',
                'student_name': 'Student',
                'student_email': 'student@example.com',
                'course_title': 'Math'
            }
        ]
        
        response = self.client.get('/api/edutech/enrollments')
        self.assertEqual(response.status_code, 200)
        import json
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data[0]['price_paid'], 0.0)

    @patch('elevateiq_app.routes.edutech_routes.get_connection')
    @patch('elevateiq_app.routes.edutech_routes.get_current_user')
    @patch('elevateiq_app.auth.get_current_user')
    def test_get_invoice_success(self, mock_get_user_auth, mock_get_user_route, mock_get_conn):
        user_info = {
            'id': 10,
            'name': 'Student User',
            'email': 'student@elevateiq.com',
            'role': 'candidate'
        }
        mock_get_user_auth.return_value = user_info
        mock_get_user_route.return_value = user_info
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchone.return_value = {
            'id': 42,
            'price_paid': 28000.0,
            'enrolled_at': None,
            'status': 'Active',
            'student_name': 'Student User',
            'student_email': 'student@elevateiq.com',
            'course_title': 'Python Bootcamp',
            'course_duration': '12 weeks'
        }
        
        response = self.client.get('/api/edutech/invoice/42')
        self.assertEqual(response.status_code, 200)
        import json
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['id'], 42)
        self.assertEqual(data['price_paid'], 28000.0)

    @patch('elevateiq_app.routes.edutech_routes.get_connection')
    @patch('elevateiq_app.routes.edutech_routes.get_current_user')
    def test_get_student_stats_success(self, mock_get_user, mock_get_conn):
        mock_get_user.return_value = {
            'id': 10,
            'name': 'Aarav Mehta',
            'email': 'rohith@gmail.com',
            'role': 'candidate'
        }
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'title': 'Full Stack Web Development', 'level': 'Beginner', 'duration': '20 weeks', 'status': 'Active', 'enrolled_at': None}
        ]
        mock_cursor.fetchone.side_effect = [
            {'current_stage': 'Mock Interview Prep', 'next_steps': 'Prep links'}, # placement_tracks
            {'count': 2} # announcements
        ]
        
        response = self.client.get('/api/edutech/student/stats')
        self.assertEqual(response.status_code, 200)
        import json
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['student_name'], 'Aarav Mehta')
        self.assertEqual(data['overall_progress'], 62)
        self.assertEqual(data['placement_stage'], 'Mock Interview Prep')

    @patch('elevateiq_app.routes.edutech_routes.get_connection')
    @patch('elevateiq_app.routes.edutech_routes.get_current_user')
    def test_submit_assignment_success(self, mock_get_user, mock_get_conn):
        mock_get_user.return_value = {
            'id': 10,
            'name': 'Aarav Mehta',
            'role': 'candidate'
        }
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchone.return_value = (1,) # assignment exists
        
        response = self.client.post('/api/edutech/assignments/1/submit', json={
            'submission_text': 'https://github.com/aarav/test-repo',
            'file_path': 'test.zip'
        })
        self.assertEqual(response.status_code, 201)
        import json
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('submitted successfully', data['message'])

    @patch('elevateiq_app.routes.edutech_routes.get_connection')
    @patch('elevateiq_app.routes.edutech_routes.get_current_user')
    def test_submit_quiz_answers_success(self, mock_get_user, mock_get_conn):
        mock_get_user.return_value = {
            'id': 10,
            'name': 'Aarav Mehta',
            'role': 'candidate'
        }
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchone.side_effect = [
            None, # quiz_attempts check (not attempted yet)
            (1, None) # quiz_attempts insert return value
        ]
        
        # mock quiz questions correct options
        mock_cursor.fetchall.return_value = [
            {'id': 101, 'correct_option': 'B'},
            {'id': 102, 'correct_option': 'B'},
            {'id': 103, 'correct_option': 'C'}
        ]
        
        response = self.client.post('/api/edutech/quizzes/1/submit', json={
            'answers': {
                '101': 'B',
                '102': 'B',
                '103': 'C'
            }
        })
        self.assertEqual(response.status_code, 201)
        import json
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['score'], 3)
        self.assertEqual(data['total_questions'], 3)
        self.assertEqual(data['percentage'], 100)

    @patch('elevateiq_app.routes.edutech_routes.get_current_user')
    @patch('os.environ.get')
    def test_advisor_chat_fallback(self, mock_env_get, mock_get_user):
        # Test case: No API key is present in environment, triggers fallback rules
        mock_env_get.return_value = None
        response = self.client.post('/api/edutech/advisor/chat', json={
            'messages': [{'role': 'user', 'content': 'Where are my quizzes?'}]
        })
        self.assertEqual(response.status_code, 200)
        import json
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('Quiz Engine', data['reply'])

    @patch('elevateiq_app.routes.edutech_routes.get_current_user')
    @patch('os.environ.get')
    @patch('groq.Groq')
    def test_advisor_chat_groq_success(self, mock_groq_class, mock_env_get, mock_get_user):
        # Test case: Groq API key is present and returns a mocked response
        mock_env_get.return_value = "gsk_testkey"
        
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_completion = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion
        
        mock_choice = MagicMock()
        mock_choice.message.content = "Select the 'Tests' tab in the left sidebar to access your quizzes."
        mock_completion.choices = [mock_choice]
        
        response = self.client.post('/api/edutech/advisor/chat', json={
            'messages': [{'role': 'user', 'content': 'How do I take test?'}]
        })
        self.assertEqual(response.status_code, 200)
        import json
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['reply'], "Select the 'Tests' tab in the left sidebar to access your quizzes.")

    @patch('elevateiq_app.routes.edutech_routes.get_connection')
    @patch('elevateiq_app.routes.edutech_routes.get_current_user')
    def test_create_quiz_success(self, mock_get_user, mock_get_conn):
        mock_get_user.return_value = {'id': 2, 'name': 'Trainer User', 'role': 'employee'}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'id': 99}
        
        response = self.client.post('/api/edutech/quizzes', json={
            'course_id': 1,
            'title': 'Test Javascript quiz',
            'duration_minutes': 20
        })
        self.assertEqual(response.status_code, 201)
        import json
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['id'], 99)

    @patch('elevateiq_app.routes.edutech_routes.get_connection')
    @patch('elevateiq_app.routes.edutech_routes.get_current_user')
    def test_create_assignment_success(self, mock_get_user, mock_get_conn):
        mock_get_user.return_value = {'id': 2, 'name': 'Trainer User', 'role': 'employee'}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'id': 88}
        
        response = self.client.post('/api/edutech/assignments', json={
            'course_id': 1,
            'title': 'Test React project',
            'description': 'Description details',
            'due_date': '2026-07-30T00:00:00'
        })
        self.assertEqual(response.status_code, 201)
        import json
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data['id'], 88)

    @patch('elevateiq_app.routes.edutech_routes.get_connection')
    @patch('elevateiq_app.routes.edutech_routes.get_current_user')
    def test_apply_student_leave_success(self, mock_get_user, mock_get_conn):
        mock_get_user.return_value = {'id': 10, 'name': 'Student User', 'role': 'candidate'}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'id': 1}
        
        response = self.client.post('/api/edutech/student/leaves', json={
            'leave_type': 'Sick',
            'start_date': '2026-08-01',
            'end_date': '2026-08-03',
            'reason': 'Medical checkup'
        })
        self.assertEqual(response.status_code, 201)
        self.assertIn(b'submitted successfully', response.data)

    @patch('elevateiq_app.routes.edutech_routes.get_connection')
    @patch('elevateiq_app.routes.edutech_routes.get_current_user')
    def test_get_student_leaves(self, mock_get_user, mock_get_conn):
        mock_get_user.return_value = {'id': 10, 'name': 'Student User', 'role': 'candidate'}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        import datetime
        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'user_id': 10,
                'leave_type': 'Sick',
                'start_date': datetime.date(2026, 8, 1),
                'end_date': datetime.date(2026, 8, 3),
                'reason': 'Medical checkup',
                'status': 'Pending',
                'approved_by': None,
                'approved_by_name': None,
                'created_at': datetime.datetime(2026, 7, 7, 12, 0, 0)
            }
        ]
        
        response = self.client.get('/api/edutech/student/leaves')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Sick', response.data)

    @patch('elevateiq_app.routes.edutech_routes.get_connection')
    @patch('elevateiq_app.routes.edutech_routes.get_current_user')
    def test_review_student_leave_success(self, mock_get_user, mock_get_conn):
        mock_get_user.return_value = {'id': 2, 'name': 'Trainer User', 'role': 'employee'}
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        
        response = self.client.put('/api/edutech/trainer/leaves/1', json={
            'status': 'Approved'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'status updated to Approved', response.data)

if __name__ == '__main__':
    unittest.main()
