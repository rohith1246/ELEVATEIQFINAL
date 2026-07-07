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

if __name__ == '__main__':
    unittest.main()
